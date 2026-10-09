# 工具 Schema

由当前注册的 52 个工具直接导出，包含别名；导出过程使用模拟适配器，没有执行机器人动作。

- `tools.schema.json`：由 LangChain 工具转换的 function calling 格式。
- `vision-tools.schema.json`：视觉 Agent 实际使用的工具目录格式。

下列参数 Schema 来自各工具的 Pydantic 参数模型；required 表示必填字段，default 表示默认值，minimum / maximum 表示取值边界，enum 表示可选值。

## wave

Wave only in response to a visibly waving or explicit greeting gesture; never use for a forward extended handshake offer.

```json
{
  "additionalProperties": false,
  "properties": {
    "arm": {
      "const": "right",
      "default": "right",
      "title": "Arm",
      "type": "string"
    }
  },
  "title": "WaveArgs",
  "type": "object"
}
```

## wave_hand

Run the SDK wave-hand action.

```json
{
  "additionalProperties": false,
  "properties": {
    "arm": {
      "const": "right",
      "default": "right",
      "title": "Arm",
      "type": "string"
    }
  },
  "title": "WaveArgs",
  "type": "object"
}
```

## handshake

Highest-priority response when a person extends a hand toward the robot around waist or lower-chest height; shake it, then release.

```json
{
  "additionalProperties": false,
  "properties": {
    "duration_s": {
      "default": 4.0,
      "maximum": 10.0,
      "minimum": 1.0,
      "title": "Duration S",
      "type": "number"
    }
  },
  "title": "HandshakeArgs",
  "type": "object"
}
```

## shake_hand

Run the SDK handshake sequence and release the arm.

```json
{
  "additionalProperties": false,
  "properties": {
    "duration_s": {
      "default": 4.0,
      "maximum": 10.0,
      "minimum": 1.0,
      "title": "Duration S",
      "type": "number"
    }
  },
  "title": "HandshakeArgs",
  "type": "object"
}
```

## two_hand_kiss

Make a two-hand kiss gesture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## left_kiss

Make a left kiss gesture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## right_kiss

Make a right kiss gesture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## hands_up

Raise both hands.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## clap

Clap both hands.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## high_five

Offer a high five.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## hug

Make a welcoming hug gesture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## heart

Make a heart with both hands.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## right_heart

Make a heart gesture with the right arm.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## reject

Make a rejection gesture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## right_hand_up

Raise the right hand.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## x_ray

Perform the SDK x-ray pose.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## high_wave

Wave with the hand raised.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## release_arm

Release the current G1 arm pose or handshake.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ArmActionArgs",
  "type": "object"
}
```

## squat

Enter the G1 squat posture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## sit

Enter the G1 sitting posture.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## stand_up

Stand up using the G1 controller.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## high_stand

Use the high standing height.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## low_stand

Use the low standing height.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## balance_stand

Enter balanced standing mode.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## move_forward

Move forward by a short bounded distance, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "distance_m": {
      "default": 0.2,
      "maximum": 0.3,
      "minimum": 0.05,
      "title": "Distance M",
      "type": "number"
    }
  },
  "title": "LinearMoveArgs",
  "type": "object"
}
```

## move_backward

Move backward by a short bounded distance, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "distance_m": {
      "default": 0.2,
      "maximum": 0.3,
      "minimum": 0.05,
      "title": "Distance M",
      "type": "number"
    }
  },
  "title": "MoveBackwardArgs",
  "type": "object"
}
```

## move_left

Step left by a short bounded distance, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "distance_m": {
      "default": 0.2,
      "maximum": 0.3,
      "minimum": 0.05,
      "title": "Distance M",
      "type": "number"
    }
  },
  "title": "LinearMoveArgs",
  "type": "object"
}
```

## move_right

Step right by a short bounded distance, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "distance_m": {
      "default": 0.2,
      "maximum": 0.3,
      "minimum": 0.05,
      "title": "Distance M",
      "type": "number"
    }
  },
  "title": "LinearMoveArgs",
  "type": "object"
}
```

## turn_left

Turn left by a small bounded angle, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "angle_deg": {
      "default": 15.0,
      "maximum": 45.0,
      "minimum": 5.0,
      "title": "Angle Deg",
      "type": "number"
    }
  },
  "title": "TurnArgs",
  "type": "object"
}
```

## turn_right

Turn right by a small bounded angle, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "angle_deg": {
      "default": 15.0,
      "maximum": 45.0,
      "minimum": 5.0,
      "title": "Angle Deg",
      "type": "number"
    }
  },
  "title": "TurnArgs",
  "type": "object"
}
```

## stop

Stop locomotion and release the current arm pose.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "StopArgs",
  "type": "object"
}
```

## stop_move

Stop the G1 locomotion controller.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "StopArgs",
  "type": "object"
}
```

## move

Move with bounded forward, lateral, and yaw velocities, then stop.

```json
{
  "additionalProperties": false,
  "properties": {
    "forward_m_s": {
      "default": 0.1,
      "maximum": 0.3,
      "minimum": -0.3,
      "title": "Forward M S",
      "type": "number"
    },
    "lateral_m_s": {
      "default": 0.0,
      "maximum": 0.3,
      "minimum": -0.3,
      "title": "Lateral M S",
      "type": "number"
    },
    "yaw_rad_s": {
      "default": 0.0,
      "maximum": 0.6,
      "minimum": -0.6,
      "title": "Yaw Rad S",
      "type": "number"
    },
    "duration_s": {
      "default": 0.5,
      "maximum": 2.0,
      "minimum": 0.1,
      "title": "Duration S",
      "type": "number"
    }
  },
  "title": "MoveArgs",
  "type": "object"
}
```

## start

Switch the G1 controller to FSM 500.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## damp

Switch the G1 controller to damping mode.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## zero_torque

Disable commanded joint torque through FSM 0.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "PostureArgs",
  "type": "object"
}
```

## wave_with_turn

Use the legacy G1 wave action while turning the body.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "EmptyControlArgs",
  "type": "object"
}
```

## continuous_gait

Enable or disable the SDK continuous gait balance mode.

```json
{
  "additionalProperties": false,
  "properties": {
    "enabled": {
      "title": "Enabled",
      "type": "boolean"
    }
  },
  "required": [
    "enabled"
  ],
  "title": "ToggleControlArgs",
  "type": "object"
}
```

## switch_move_mode

Switch the SDK Move call between timed and continuous mode.

```json
{
  "additionalProperties": false,
  "properties": {
    "enabled": {
      "title": "Enabled",
      "type": "boolean"
    }
  },
  "required": [
    "enabled"
  ],
  "title": "ToggleControlArgs",
  "type": "object"
}
```

## set_speed_mode

Set the model-specific integer G1 speed mode.

```json
{
  "additionalProperties": false,
  "properties": {
    "mode": {
      "maximum": 255,
      "minimum": 0,
      "title": "Mode",
      "type": "integer"
    }
  },
  "required": [
    "mode"
  ],
  "title": "SpeedModeArgs",
  "type": "object"
}
```

## set_fsm_id

Set an explicit G1 locomotion FSM ID.

```json
{
  "additionalProperties": false,
  "properties": {
    "fsm_id": {
      "maximum": 999999,
      "minimum": 0,
      "title": "Fsm Id",
      "type": "integer"
    }
  },
  "required": [
    "fsm_id"
  ],
  "title": "FsmIdArgs",
  "type": "object"
}
```

## set_balance_mode

Set the integer G1 balance mode.

```json
{
  "additionalProperties": false,
  "properties": {
    "balance_mode": {
      "maximum": 255,
      "minimum": 0,
      "title": "Balance Mode",
      "type": "integer"
    }
  },
  "required": [
    "balance_mode"
  ],
  "title": "BalanceModeArgs",
  "type": "object"
}
```

## set_swing_height

Set the G1 swing height in SDK units.

```json
{
  "additionalProperties": false,
  "properties": {
    "swing_height": {
      "title": "Swing Height",
      "type": "number"
    }
  },
  "required": [
    "swing_height"
  ],
  "title": "SwingHeightArgs",
  "type": "object"
}
```

## set_stand_height

Set the G1 stand height in SDK units.

```json
{
  "additionalProperties": false,
  "properties": {
    "stand_height": {
      "title": "Stand Height",
      "type": "number"
    }
  },
  "required": [
    "stand_height"
  ],
  "title": "StandHeightArgs",
  "type": "object"
}
```

## set_velocity

Send one bounded SDK velocity command with a finite duration.

```json
{
  "additionalProperties": false,
  "properties": {
    "vx": {
      "maximum": 1.0,
      "minimum": -1.0,
      "title": "Vx",
      "type": "number"
    },
    "vy": {
      "maximum": 1.0,
      "minimum": -1.0,
      "title": "Vy",
      "type": "number"
    },
    "omega": {
      "maximum": 2.0,
      "minimum": -2.0,
      "title": "Omega",
      "type": "number"
    },
    "duration": {
      "default": 1.0,
      "maximum": 10.0,
      "minimum": 0.1,
      "title": "Duration",
      "type": "number"
    }
  },
  "required": [
    "vx",
    "vy",
    "omega"
  ],
  "title": "SetVelocityArgs",
  "type": "object"
}
```

## move_sdk

Call the SDK's overloaded LocoClient.move API directly.

```json
{
  "additionalProperties": false,
  "description": "Arguments for the SDK's overloaded ``LocoClient.move`` call.",
  "properties": {
    "vx": {
      "maximum": 1.0,
      "minimum": -1.0,
      "title": "Vx",
      "type": "number"
    },
    "vy": {
      "maximum": 1.0,
      "minimum": -1.0,
      "title": "Vy",
      "type": "number"
    },
    "vyaw": {
      "maximum": 2.0,
      "minimum": -2.0,
      "title": "Vyaw",
      "type": "number"
    },
    "continuous_move": {
      "default": false,
      "title": "Continuous Move",
      "type": "boolean"
    }
  },
  "required": [
    "vx",
    "vy",
    "vyaw"
  ],
  "title": "SdkMoveArgs",
  "type": "object"
}
```

## set_task_id

Set an explicit G1 arm-task ID through LocoClient.

```json
{
  "additionalProperties": false,
  "properties": {
    "task_id": {
      "maximum": 255,
      "minimum": 0,
      "title": "Task Id",
      "type": "integer"
    }
  },
  "required": [
    "task_id"
  ],
  "title": "TaskIdArgs",
  "type": "object"
}
```

## switch_to_user_ctrl

Switch G1 control to the user controller.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "EmptyControlArgs",
  "type": "object"
}
```

## switch_to_internal_ctrl

Switch G1 control to an SDK internal FSM mode.

```json
{
  "additionalProperties": false,
  "properties": {
    "mode": {
      "enum": [
        "last",
        "passive",
        "walkrun"
      ],
      "title": "Mode",
      "type": "string"
    }
  },
  "required": [
    "mode"
  ],
  "title": "InternalControlArgs",
  "type": "object"
}
```

## fsm_api

Send a raw JSON parameter to the G1 locomotion FSM API.

```json
{
  "additionalProperties": false,
  "properties": {
    "parameter": {
      "maxLength": 4096,
      "minLength": 1,
      "title": "Parameter",
      "type": "string"
    }
  },
  "required": [
    "parameter"
  ],
  "title": "FsmApiArgs",
  "type": "object"
}
```

## execute_custom_arm_action

Execute a named G1 teach/custom arm action.

```json
{
  "additionalProperties": false,
  "properties": {
    "action_name": {
      "maxLength": 256,
      "minLength": 1,
      "title": "Action Name",
      "type": "string"
    }
  },
  "required": [
    "action_name"
  ],
  "title": "CustomArmActionArgs",
  "type": "object"
}
```

## stop_custom_arm_action

Stop the currently running named G1 teach/custom arm action.

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "EmptyControlArgs",
  "type": "object"
}
```
