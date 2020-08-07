import asyncio
import time

import pytest

from src.simulator.simulator_protocol import FarmNewBlockProtocol
from src.types.peer_info import PeerInfo
from src.util.ints import uint16, uint64, uint32
from src.wallet.rl_wallet.rl_wallet import RLWallet
from src.wallet.transaction_record import TransactionRecord
from tests.setup_nodes import setup_simulators_and_wallets
from tests.time_out_assert import time_out_assert


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


class TestCCWallet:
    @pytest.fixture(scope="function")
    async def two_wallet_nodes(self):
        async for _ in setup_simulators_and_wallets(
            1, 2, {"COINBASE_FREEZE_PERIOD": 0}
        ):
            yield _

    @pytest.mark.asyncio
    async def test_create_rl_coin(self, two_wallet_nodes):
        num_blocks = 4
        full_nodes, wallets = two_wallet_nodes
        full_node_1, server_1 = full_nodes[0]
        wallet_node, server_2 = wallets[0]
        wallet_node_1, wallet_server_1 = wallets[1]

        wallet = wallet_node.wallet_state_manager.main_wallet

        ph = await wallet.get_new_puzzlehash()

        await server_2.start_client(PeerInfo("localhost", uint16(server_1._port)), None)
        await wallet_server_1.start_client(
            PeerInfo("localhost", uint16(server_1._port)), None
        )

        for i in range(0, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        rl_admin: RLWallet = await RLWallet.create_rl_admin(
            wallet_node.wallet_state_manager
        )

        rl_user: RLWallet = await RLWallet.create_rl_user(
            wallet_node_1.wallet_state_manager
        )
        interval = uint64(2)
        limit = uint64(1)
        amount = uint64(100)
        await rl_admin.admin_create_coin(
            interval, limit, rl_user.rl_info.user_pubkey.hex(), amount
        )
        origin = rl_admin.rl_info.rl_origin
        admin_pubkey = rl_admin.rl_info.admin_pubkey

        await rl_user.set_user_info(
            interval,
            limit,
            origin.parent_coin_info.hex(),
            origin.puzzle_hash.hex(),
            origin.amount,
            admin_pubkey.hex(),
        )

        for i in range(0, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(32 * b"\0"))

        for i in range(0, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(32 * b"\0"))

        await time_out_assert(15, rl_user.get_confirmed_balance, 100)
        balance = await rl_user.rl_available_balance()

        tx_record = await rl_user.rl_generate_signed_transaction(1, 32 * b"\0")
        now = uint64(int(time.time()))

        await wallet_node_1.wallet_state_manager.main_wallet.push_transaction(tx_record)

        for i in range(0, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(32 * b"\0"))

        balance = await rl_user.get_confirmed_balance()
        print(balance)

        await time_out_assert(15, rl_user.get_confirmed_balance, 99)

        rl_user.rl_get_aggregation_puzzlehash(rl_user.get_new_puzzle())
        # rl_admin.rl_generate_signed_aggregation_transaction()