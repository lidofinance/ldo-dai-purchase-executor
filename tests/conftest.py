import pytest
from brownie import chain, Wei, ZERO_ADDRESS

from scripts.deploy import deploy_and_start_dao_vote

from utils.config import (
    ldo_token_address,
    lido_dao_acl_address,
    lido_dao_agent_address,
    lido_dao_voting_address,
    lido_dao_token_manager_address,
    dai_token_address
)


@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


@pytest.fixture(scope='module')
def ldo_holder(accounts):
    return accounts.at('0xAD4f7415407B83a081A0Bee22D05A8FDC18B42da', force=True)


@pytest.fixture(scope='module')
def stranger(accounts):
    return accounts[9]

@pytest.fixture(scope='module')
def dai_token(interface):
    return interface.Dai(dai_token_address)

@pytest.fixture(scope='module')
def dao_acl(interface):
    return interface.ACL(lido_dao_acl_address)


@pytest.fixture(scope='module')
def dao_voting(interface):
    return interface.Voting(lido_dao_voting_address)


@pytest.fixture(scope='module')
def dao_token_manager(interface):
    return interface.TokenManager(lido_dao_token_manager_address)


# Lido DAO Agent app
@pytest.fixture(scope='module')
def dao_agent(interface):
    return interface.Agent(lido_dao_agent_address)


@pytest.fixture(scope='module')
def ldo_token(interface):
    return interface.ERC20(ldo_token_address)


class Helpers:
    accounts = None
    eth_banker = None
    dao_voting = None
    dai_token = None

    @staticmethod
    def fund_with_eth(addr, amount = '1000 ether'):
        Helpers.eth_banker.transfer(to=addr, amount=amount)

    @staticmethod
    def fund_with_dai(addr, amount):
        stranger = Helpers.accounts.at('0x075e72a5edf65f0a5f44699c7654c1a76941ddc8', force=True)
        Helpers.dai_token.transfer(addr, amount, { 'from': stranger })

    @staticmethod
    def filter_events_from(addr, events):
      return list(filter(lambda evt: evt.address == addr, events))

    @staticmethod
    def assert_single_event_named(evt_name, tx, evt_keys_dict = None):
      receiver_events = Helpers.filter_events_from(tx.receiver, tx.events[evt_name])
      assert len(receiver_events) == 1
      if evt_keys_dict is not None:
        assert dict(receiver_events[0]) == evt_keys_dict
      return receiver_events[0]

    @staticmethod
    def pass_and_exec_dao_vote(vote_id):
        print(f'executing vote {vote_id}')

        # together these accounts hold 15% of LDO total supply
        ldo_holders = [
            '0x3e40d73eb977dc6a537af587d48316fee66e9c8c',
            '0xb8d83908aab38a159f3da47a59d84db8e1838712',
            '0xa2dfc431297aee387c05beef507e5335e684fbcd'
        ]

        helper_acct = Helpers.accounts[0]

        for holder_addr in ldo_holders:
            print(f'voting from {holder_addr}')
            helper_acct.transfer(holder_addr, '0.1 ether')
            account = Helpers.accounts.at(holder_addr, force=True)
            Helpers.dao_voting.vote(vote_id, True, False, {'from': account})

        # wait for the vote to end
        chain.sleep(3 * 60 * 60 * 24)
        chain.mine()

        assert Helpers.dao_voting.canExecute(vote_id)
        Helpers.dao_voting.executeVote(vote_id, {'from': helper_acct})

        print(f'vote {vote_id} executed')



@pytest.fixture(scope='module')
def helpers(accounts, dao_voting, dai_token):
    Helpers.accounts = accounts
    Helpers.eth_banker = accounts.at('0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8', force=True)
    Helpers.dao_voting = dao_voting
    Helpers.dai_token = dai_token
    return Helpers


@pytest.fixture(scope='module')
def deploy_executor_and_pass_dao_vote(accounts, ldo_holder, ldo_token, dao_acl, dao_token_manager, helpers):
    def deploy(
        dai_to_ldo_rate,
        vesting_start_delay,
        vesting_end_delay,
        offer_expiration_delay,
        ldo_purchasers,
        allocations_total
    ):
        (executor, vote_id) = deploy_and_start_dao_vote(
            {'from': ldo_holder},
            dai_to_ldo_rate=dai_to_ldo_rate,
            vesting_start_delay=vesting_start_delay,
            vesting_end_delay=vesting_end_delay,
            offer_expiration_delay=offer_expiration_delay,
            ldo_purchasers=ldo_purchasers,
            allocations_total=allocations_total
        )

        helpers.pass_and_exec_dao_vote(vote_id)

        total_ldo_assignment = sum([ p[1] for p in ldo_purchasers ])
        assert ldo_token.balanceOf(executor) == total_ldo_assignment

        ldo_assign_role = dao_token_manager.ASSIGN_ROLE()
        assert dao_acl.hasPermission(executor, dao_token_manager, ldo_assign_role)

        return executor

    return deploy
