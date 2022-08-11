import sys
from brownie import ZERO_ADDRESS
from utils import config

try:
    from brownie import PurchaseExecutor, interface
except ImportError:
    print("You're probably running inside Brownie console. Please call:")
    print("set_console_globals(interface=interface, PurchaseExecutor=PurchaseExecutor)")


def set_console_globals(**kwargs):
    global PurchaseExecutor
    global interface
    PurchaseExecutor = kwargs['PurchaseExecutor']
    interface = kwargs['interface']


from utils.dao import (
    create_vote,
    encode_token_transfer,
    encode_permission_grant,
    encode_permission_revoke,
    encode_call_script
)

from utils.config import (
    ldo_token_address,
    lido_dao_acl_address,
    lido_dao_voting_address,
    lido_dao_finance_address,
    lido_dao_token_manager_address
)

from purchase_config import (
    MAX_PURCHASERS,
    DAI_TO_LDO_RATE,
    VESTING_START_DELAY,
    VESTING_END_DELAY,
    OFFER_EXPIRATION_DELAY,
    LDO_PURCHASERS,
    TOTAL_LDO_SOLD
)

def main():
    deployer = config.get_deployer_account(config.get_is_live())
    
    print("Deployer:", deployer)


    sys.stdout.write("Proceed? [y/n]: ")
    if not config.prompt_bool():
        print("Aborting")
        return

    tx_params = {"from": deployer, "max_fee": "100 gwei", "priority_fee": "2 gwei"}

    (executor, vote_id) = deploy_and_start_dao_vote(
        tx_params
    )

    print("Executor:", executor)
    print("VoteId:", vote_id)

def propose_vesting_manager_contract(
    tx_params,
    manager_address,
    total_ldo_amount=TOTAL_LDO_SOLD,
    ldo_transfer_reference='Transfer LDO tokens to be sold for DAI'
):
    acl = interface.ACL(lido_dao_acl_address)
    voting = interface.Voting(lido_dao_voting_address)
    finance = interface.Finance(lido_dao_finance_address)
    token_manager = interface.TokenManager(lido_dao_token_manager_address)

    evm_script = encode_call_script([
        encode_token_transfer(
            token_address=ldo_token_address,
            recipient=manager_address,
            amount=total_ldo_amount,
            reference=ldo_transfer_reference,
            finance=finance
        ),
        encode_permission_grant(
            target_app=token_manager,
            permission_name='ASSIGN_ROLE',
            grant_to=manager_address,
            acl=acl
        )
    ])
    return create_vote(
        voting=voting,
        token_manager=token_manager,
        vote_desc=f'Make {manager_address} a vesting manager for total {total_ldo_amount} LDO',
        evm_script=evm_script,
        tx_params=tx_params
    )


def deploy(
    tx_params,
    dai_to_ldo_rate=DAI_TO_LDO_RATE,
    vesting_start_delay=VESTING_START_DELAY,
    vesting_end_delay=VESTING_END_DELAY,
    offer_expiration_delay=OFFER_EXPIRATION_DELAY,
    ldo_purchasers=LDO_PURCHASERS,
    total_ldo_sold=TOTAL_LDO_SOLD
):
    zero_padding_len = MAX_PURCHASERS - len(ldo_purchasers)
    ldo_recipients = [ p[0] for p in ldo_purchasers ] + [ZERO_ADDRESS] * zero_padding_len
    ldo_allocations = [ p[1] for p in ldo_purchasers ] + [0] * zero_padding_len

    return PurchaseExecutor.deploy(
        dai_to_ldo_rate,
        vesting_start_delay,
        vesting_end_delay,
        offer_expiration_delay,
        ldo_recipients,
        ldo_allocations,
        total_ldo_sold,
        tx_params
    )


def deploy_and_start_dao_vote(
    tx_params,
    dai_to_ldo_rate=DAI_TO_LDO_RATE,
    vesting_start_delay=VESTING_START_DELAY,
    vesting_end_delay=VESTING_END_DELAY,
    offer_expiration_delay=OFFER_EXPIRATION_DELAY,
    ldo_purchasers=LDO_PURCHASERS,
    total_ldo_sold = TOTAL_LDO_SOLD
):
    executor = deploy(
        tx_params=tx_params,
        dai_to_ldo_rate=dai_to_ldo_rate,
        vesting_start_delay=vesting_start_delay,
        vesting_end_delay=vesting_end_delay,
        offer_expiration_delay=offer_expiration_delay,
        ldo_purchasers=ldo_purchasers,
        total_ldo_sold=total_ldo_sold
    )

    (vote_id, _) = propose_vesting_manager_contract(
        tx_params=tx_params,
        manager_address=executor.address,
        total_ldo_amount=total_ldo_sold,
        ldo_transfer_reference='Transfer LDO tokens to be sold for DAI'
    )

    return (executor, vote_id)


