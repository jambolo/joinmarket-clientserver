# Implementation of proposal as per
# https://gist.github.com/AdamISZ/2c13fb5819bd469ca318156e2cf25d79
# (BIP SNICKER)
# TODO: BIP69 is removed in this implementation, will update BIP draft.

from jmbitcoin.secp256k1_ecies import *
from jmbitcoin.secp256k1_main import *
from jmbitcoin.secp256k1_transaction import *
from collections import Counter

SNICKER_MAGIC_BYTES = b'SNICKER'

# Flags may be added in future versions
SNICKER_FLAG_NONE = b"\x00"

def snicker_pubkey_tweak(pub, tweak):
    """ use secp256k1 library to perform tweak.
    Both `pub` and `tweak` are expected as byte strings
    (33 and 32 bytes respectively).
    Return value is also a 33 byte string serialization
    of the resulting pubkey (compressed).
    """
    base_pub = secp256k1.PublicKey(pub)
    return base_pub.add(tweak).format()

def snicker_privkey_tweak(priv, tweak):
    """ use secp256k1 library to perform tweak.
    Both `priv` and `tweak` are expected as byte strings
    (32 or 33 and 32 bytes respectively).
    Return value isa 33 byte string serialization
    of the resulting private key/secret (with compression flag).
    """
    if len(priv) == 33 and priv[-1] == 1:
        priv = priv[:-1]
    base_priv = secp256k1.PrivateKey(priv)
    return base_priv.add(tweak).secret + b'\x01'

def verify_snicker_output(tx, pub, tweak, spk_type="p2wpkh"):
    """ A convenience function to check that one output address in a transaction
    is a SNICKER-type tweak of an existing key. Returns the index of the output
    for which this is True (and there must be only 1), and the derived spk,
    or -1 and None if it is not found exactly once.
    Only standard segwit spk types (as used in Joinmarket) are supported.
    """
    assert isinstance(tx, btc.CTransaction)
    expected_destination_pub = snicker_pubkey_tweak(pub, tweak)
    if spk_type == "p2wpkh":
        expected_destination_spk = pubkey_to_p2wpkh_script(
            expected_destination_pub)
    elif spk_type == "p2sh-p2wpkh":
        expected_destination_spk = pubkey_to_p2sh_p2wpkh_script(
            expected_destination_pub)
    else:
        assert False, "JM SNICKER only supports p2sh/p2wpkh"
    found = 0
    for i, o in enumerate(tx.vout):
        if o.scriptPubKey == expected_destination_spk:
            found += 1
            found_index = i
    if found != 1:
        return -1, None
    return found_index, expected_destination_spk

def is_snicker_tx(tx, snicker_version=bytes([1])):
    """ Returns True if the CTransaction object `tx`
    fits the pattern of a SNICKER coinjoin of type
    defined in `snicker_version`, or False otherwise.
    """
    if not snicker_version == b"\x01":
        raise NotImplementedError("Only v1 SNICKER currently implemented.")
    return is_snicker_v1_tx(tx)

def is_snicker_v1_tx(tx):
    """ We expect:
    * 2 equal outputs, same script type, pubkey hash variant.
    * 1 other output (0 is negligible probability hence ignored - if it
      was included it would create a lot of false positives).
    * Exactly 2 inputs, same script type, pubkey hash variant.
    * Input sequence numbers are both 0xffffffff
    * nVersion 2
    * nLockTime 0
    The above rules are for matching the v1 variant of SNICKER.
    """
    assert isinstance(tx, CTransaction)
    if tx.nVersion != 2:
        return False
    if tx.nLockTime != 0:
        return False
    if len(tx.vin) != 2:
        return False
    if len(tx.vout) != 3:
        return False
    for vi in tx.vin:
        if vi.nSequence != 0xffffffff:
            return False
    # identify if there are two equal sized outs
    c = Counter([vo.nValue for vo in tx.vout])
    equal_out = -1
    for x in c:
        if c[x] not in [1, 2]:
            # note three equal outs technically agrees
            # with spec, but negligible prob and will
            # create false positives.
            return False
        if c[x] == 2:
            equal_out = x

    if equal_out == -1:
        return False

    # ensure that the equal sized outputs have the
    # same script type
    matched_spk = None
    for vo in tx.vout:
        if vo.nValue == equal_out:
            if not matched_spk:
                matched_spk = btc.CCoinAddress.from_scriptPubKey(
                    vo.scriptPubKey).get_scriptPubKey_type()
            else:
                if not btc.CCoinAddress.from_scriptPubKey(
                    vo.scriptPubKey).get_scriptPubKey_type() == matched_spk:
                    return False
    assert matched_spk
    return True
