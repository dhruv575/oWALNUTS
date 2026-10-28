"""Integer v2 liquidity arithmetic for ordinary tokens; not an EVM/event replica.

Balances must include donations. Burn assumes transfers debit exactly the amount
sent, without rebasing, transfer taxes or callbacks changing pool balances.
"""
from math import isqrt

U256=2**256-1
U112=2**112-1


def uint(value, maximum=U256):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError('Unsigned integer bound')
    return value


def add(a,b):return uint(a+b)
def mul(a,b):return uint(a*b)
def sub(a,b):return uint(a-b)


def protocol_fee(reserves, supply, k_last, fee_on):
    if len(reserves)!=2 or type(fee_on) is not bool:raise ValueError('State shape')
    for r in reserves:uint(r,U112)
    uint(supply);uint(k_last)
    minted=0
    if fee_on and k_last:
        root=isqrt(mul(*reserves));previous=isqrt(k_last)
        if root>previous:
            minted=mul(supply,root-previous)//add(mul(root,5),previous)
    return dict(minted=minted,supply=add(supply,minted),k_last=k_last if fee_on else 0)


def mint(reserves, balances, supply, k_last, fee_on):
    if len(balances)!=2:raise ValueError('Balance shape')
    for b in balances:uint(b,U112)
    fee=protocol_fee(reserves,supply,k_last,fee_on)
    amounts=[sub(b,r) for b,r in zip(balances,reserves)]
    adjusted=fee['supply'];locked=0
    if adjusted==0:
        liquidity=sub(isqrt(mul(*amounts)),1000);locked=1000
    else:
        if min(reserves)==0:raise ValueError('Division by zero reserve')
        liquidity=min(mul(amounts[i],adjusted)//reserves[i] for i in range(2))
    if liquidity==0:raise ValueError('Insufficient minted liquidity')
    total=add(add(adjusted,locked),liquidity)
    return dict(reserves=list(balances),supply=total,liquidity=liquidity,
                locked_liquidity=locked,protocol_liquidity=fee['minted'],amounts=amounts,
                k_last=mul(*balances) if fee_on else fee['k_last'])


def burn(reserves, balances, supply, k_last, fee_on, liquidity):
    if len(balances)!=2:raise ValueError('Balance shape')
    for b in balances:uint(b)
    uint(liquidity)
    if liquidity>supply:raise ValueError('Burn exceeds pre-fee supply')
    fee=protocol_fee(reserves,supply,k_last,fee_on);adjusted=fee['supply']
    if adjusted==0:raise ValueError('Division by zero supply')
    amounts=[mul(liquidity,b)//adjusted for b in balances]
    if min(amounts)==0:raise ValueError('Insufficient burned liquidity')
    after=[sub(b,a) for b,a in zip(balances,amounts)]
    for b in after:uint(b,U112)
    return dict(reserves=after,supply=sub(adjusted,liquidity),amounts=amounts,
                protocol_liquidity=fee['minted'],k_last=mul(*after) if fee_on else fee['k_last'])
