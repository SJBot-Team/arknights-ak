# 关卡探明台账（关卡-关联单位-关联机制一次探明）

共 12 关，成功 12

| 关卡 | 内部目录 | 生命 | 地图 | 路线 | 敌人种类 | 出怪动作 | 机制(runes) | randomSeed |
|---|---|---|---|---|---|---|---|---|
| 1-1 | `obt/main/level_main_01-01` | 10 | 7×9 | 19 | 6 | 16 | gbuff_lifepoint, ebuff_attribute, gbuff_placable_char_num | 978975386 |
| 1-2 | `obt/main/level_main_01-02` | 10 | 8×10 | 23 | 6 | 22 | gbuff_lifepoint, gbuff_placable_char_num, ebuff_attribute | 1924903387 |
| 1-3 | `obt/main/level_main_01-03` | 10 | 7×11 | 22 | 6 | 21 | gbuff_lifepoint, ebuff_attribute | 1654081763 |
| 1-4 | `obt/main/level_main_01-04` | 10 | 7×11 | 32 | 7 | 31 | gbuff_lifepoint, ebuff_attribute, cbuff_char_cost | 916562971 |
| 1-5 | `obt/main/level_main_01-05` | 10 | 8×11 | 41 | 6 | 40 | gbuff_lifepoint, ebuff_attribute | 429076025 |
| 1-6 | `obt/main/level_main_01-06` | 8 | 7×10 | 40 | 3 | 35 | gbuff_lifepoint, ebuff_attribute, cbuff_token_initial_cnt | 429076025 |
| 1-7 | `obt/main/level_main_01-07` | 10 | 7×11 | 27 | 6 | 24 | gbuff_lifepoint, ebuff_attribute, cbuff_cost_recovery | 1924903387 |
| 1-8 | `obt/main/level_main_01-08` | 8 | 7×11 | 32 | 8 | 29 | gbuff_lifepoint, ebuff_attribute, ebuff_skill_cd | 1654081763 |
| 1-9 | `obt/main/level_main_01-09` | 8 | 8×10 | 26 | 4 | 25 | gbuff_lifepoint, ebuff_attribute, cbuff_excluded | 1944566651 |
| 1-10 | `obt/main/level_main_01-10` | 8 | 8×10 | 29 | 7 | 28 | gbuff_lifepoint, ebuff_attribute, ebuff_attack_radius | 1944566651 |
| 1-11 | `obt/main/level_main_01-11` | 8 | 7×11 | 21 | 7 | 16 | gbuff_lifepoint, ebuff_attribute, ebuff_skill_cd | 1654081763 |
| 1-12 | `obt/main/level_main_01-12` | 5 | 8×11 | 30 | 6 | 27 | gbuff_lifepoint, ebuff_attribute, cbuff_char_cost | 586487713 |

## 各关机制的 blackboard 明细

### 1-1（`obt/main/level_main_01-01`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]
- `gbuff_placable_char_num`: [{"key": "value", "value": -4.0, "valueStr": null}]

### 1-2（`obt/main/level_main_01-02`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `gbuff_placable_char_num`: [{"key": "value", "value": -2.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]

### 1-3（`obt/main/level_main_01-03`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.8, "valueStr": null}]

### 1-4（`obt/main/level_main_01-04`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]
- `cbuff_char_cost`: [{"key": "scale", "value": 3.0, "valueStr": null}]

### 1-5（`obt/main/level_main_01-05`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "move_speed", "value": 2.0, "valueStr": null}, {"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]

### 1-6（`obt/main/level_main_01-06`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]
- `cbuff_token_initial_cnt`: [{"key": "value", "value": -4.0, "valueStr": null}]

### 1-7（`obt/main/level_main_01-07`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]
- `cbuff_cost_recovery`: [{"key": "scale", "value": 2.0, "valueStr": null}]

### 1-8（`obt/main/level_main_01-08`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.5, "valueStr": null}]
- `ebuff_skill_cd`: [{"key": "scale", "value": 0.35, "valueStr": null}]

### 1-9（`obt/main/level_main_01-09`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]
- `cbuff_excluded`: []

### 1-10（`obt/main/level_main_01-10`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}]
- `ebuff_attack_radius`: [{"key": "range_scale", "value": 2.0, "valueStr": null}]

### 1-11（`obt/main/level_main_01-11`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.5, "valueStr": null}]
- `ebuff_skill_cd`: [{"key": "scale", "value": 0.35, "valueStr": null}]

### 1-12（`obt/main/level_main_01-12`）
- `gbuff_lifepoint`: [{"key": "value", "value": 1.0, "valueStr": null}]
- `ebuff_attribute`: [{"key": "atk", "value": 1.2, "valueStr": null}, {"key": "max_hp", "value": 1.2, "valueStr": null}, {"key": "def", "value": 1.2, "valueStr": null}]
- `cbuff_char_cost`: [{"key": "scale", "value": 2.0, "valueStr": null}]
