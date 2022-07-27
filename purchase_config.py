import csv

DAI_TO_LDO_RATE_PRECISION = 10**18

#
# Proposal 
#
# https://research.lido.fi/t/treasury-diversification-2/2570
#
# 20M LDO in 29,043,051.43 DAI
# 1.4521525715 DAI in one LDO
DAI_TO_LDO_RATE = DAI_TO_LDO_RATE_PRECISION * (20 * 10**6) // 21600

VESTING_START_DELAY = 1 * 60 * 60 * 24 * 365 # one year
VESTING_END_DELAY = 2 * 60 * 60 * 24 * 365 # two years
OFFER_EXPIRATION_DELAY = 2629746 # one month

ALLOCATIONS_TOTAL = 99064814814814816060000000


def read_csv_purchasers(filename):
    data = [ (item[0], int(item[1])) for item in read_csv_data(filename) ]
    allocations_total = sum([ item[1] for item in data ])
    assert allocations_total == ALLOCATIONS_TOTAL, f'invalid allocations sum: expected {ALLOCATIONS_TOTAL}, actual {allocations_total}'
    return data


def read_csv_data(filename):
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"', skipinitialspace=True)
        return list(reader)


LDO_PURCHASERS = read_csv_purchasers('purchasers.csv')
