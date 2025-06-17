from construct import Struct, Const, Int8ub, Bytes, this, Int32ub


class DeviceStructs:
    magic = Const(b"PRD")

    header = Struct(
        "signature" / magic,
        "version" / Int8ub,
    )

    # was never in production
    v1 = Struct(
        "signature" / magic,
        "version" / Int8ub,
        "group_key_length" / Int32ub,
        "group_key" / Bytes(this.group_key_length),
        "group_certificate_length" / Int32ub,
        "group_certificate" / Bytes(this.group_certificate_length)
    )

    v2 = Struct(
        "signature" / magic,
        "version" / Int8ub,
        "group_certificate_length" / Int32ub,
        "group_certificate" / Bytes(this.group_certificate_length),
        "encryption_key" / Bytes(96),
        "signing_key" / Bytes(96),
    )

    v3 = Struct(
        "signature" / magic,
        "version" / Int8ub,
        "group_key" / Bytes(96),
        "encryption_key" / Bytes(96),
        "signing_key" / Bytes(96),
        "group_certificate_length" / Int32ub,
        "group_certificate" / Bytes(this.group_certificate_length),
    )
