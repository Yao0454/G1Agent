"""Unitree G1 action identifiers copied from the installed SDK2 headers."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class G1ArmActionSpec:
    skill_name: str
    sdk_name: str
    action_id: int
    description: str


G1_ARM_ACTION_SPECS = (
    G1ArmActionSpec(
        "two_hand_kiss",
        "two-hand kiss",
        11,
        "Make a two-hand kiss gesture.",
    ),
    G1ArmActionSpec("left_kiss", "left kiss", 12, "Make a left kiss gesture."),
    # The installed Unitree header maps both left and right kiss to ID 12.
    G1ArmActionSpec("right_kiss", "right kiss", 12, "Make a right kiss gesture."),
    G1ArmActionSpec("hands_up", "hands up", 15, "Raise both hands."),
    G1ArmActionSpec("clap", "clap", 17, "Clap both hands."),
    G1ArmActionSpec("high_five", "high five", 18, "Offer a high five."),
    G1ArmActionSpec("hug", "hug", 19, "Make a welcoming hug gesture."),
    G1ArmActionSpec("heart", "heart", 20, "Make a heart with both hands."),
    G1ArmActionSpec(
        "right_heart",
        "right heart",
        21,
        "Make a heart gesture with the right arm.",
    ),
    G1ArmActionSpec("reject", "reject", 22, "Make a rejection gesture."),
    G1ArmActionSpec(
        "right_hand_up",
        "right hand up",
        23,
        "Raise the right hand.",
    ),
    G1ArmActionSpec("x_ray", "x-ray", 24, "Perform the SDK x-ray pose."),
    G1ArmActionSpec("wave", "face wave", 25, "Wave the right hand."),
    G1ArmActionSpec("high_wave", "high wave", 26, "Wave with the hand raised."),
    G1ArmActionSpec(
        "handshake",
        "shake hand",
        27,
        "Offer and perform a right-hand handshake.",
    ),
    G1ArmActionSpec("release_arm", "release arm", 99, "Release an arm pose."),
)

G1_ARM_ACTION_NAMES: dict[int, tuple[str, ...]] = {}
for _spec in G1_ARM_ACTION_SPECS:
    G1_ARM_ACTION_NAMES[_spec.action_id] = (
        *G1_ARM_ACTION_NAMES.get(_spec.action_id, ()),
        _spec.sdk_name,
    )


__all__ = [
    "G1_ARM_ACTION_NAMES",
    "G1_ARM_ACTION_SPECS",
    "G1ArmActionSpec",
]
