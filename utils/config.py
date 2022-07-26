import os
import sys
from brownie import network, accounts, rpc


ldo_token_address = '0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32'
lido_dao_acl_address = '0x9895F0F17cc1d1891b6f18ee0b483B6f221b37Bb'
lido_dao_agent_address = '0x3e40D73EB977Dc6a537aF587D48316feE66E9C8c'
lido_dao_finance_address = '0xB9E5CBB9CA5b0d659238807E84D0176930753d86'
lido_dao_voting_address = '0x2e59A20f205bB85a89C53f1936454680651E618e'
lido_dao_token_manager_address = '0xf73a1260d222f447210581DDf212D915c09a3249'
dai_token_address = '0x6B175474E89094C44Da98b954EedeAC495271d0F'

ldo_vote_executors_for_tests = [
    '0x3e40d73eb977dc6a537af587d48316fee66e9c8c',
    '0xb8d83908aab38a159f3da47a59d84db8e1838712',
    '0xa2dfc431297aee387c05beef507e5335e684fbcd'
]

def get_is_live():
    return not rpc.is_active()


def get_deployer_account(is_live):
    if is_live and 'DEPLOYER' not in os.environ:
        raise EnvironmentError('Please set DEPLOYER env variable to the deployer account name')

    return accounts.load(os.environ['DEPLOYER']) if is_live else accounts.at(
        ldo_vote_executors_for_tests[0], force=True)


def prompt_bool():
    choice = input().lower()
    if choice in {'yes', 'y'}:
       return True
    elif choice in {'no', 'n'}:
       return False
    else:
       sys.stdout.write("Please respond with 'yes' or 'no'")
