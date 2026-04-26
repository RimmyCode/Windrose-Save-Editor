from __future__ import annotations

TALENT_NAMES: dict[str, str] = {
    "Talent_Crusher_Berserk": "Berserk",
    "Talent_Crusher_CrudeDamage": "Bonecrusher",
    "Talent_Crusher_DamageForDeathNearby": "Dominating Presence",
    "Talent_Crusher_DamageForMultipleTargets": "Momentum",
    "Talent_Crusher_DamageResistWithTwoHandedWpn": "Storm Bracing",
    "Talent_Crusher_TemporalHPHealBuff": "Retribution",
    "Talent_Crusher_TwoHandedDamage": "Massive",
    "Talent_Crusher_TwoHandedMeleeCritChance": "Executioner's Aim",
    "Talent_Crusher_TwoHandedStaminaReduced": "Perfected Form",
    "Talent_Fencer_ConsecutiveMeleeHitsBonus": "Deadly Finale",
    "Talent_Fencer_CritChanceForPerfectBlock": "Perfect Counter",
    "Talent_Fencer_DamageForSoloEnemy": "Duelist",
    "Talent_Fencer_HealForKill": "Executioner's Grace",
    "Talent_Fencer_LessStaminaForDash": "Agile",
    "Talent_Fencer_OneHandedDamage": "Quick Strikes",
    "Talent_Fencer_OneHandedMeleeCritChance": "Surgical Cuts",
    "Talent_Fencer_PassiveReloadBoostForPerfectBlock": "Disciplined Fencer",
    "Talent_Fencer_PassiveReloadBoostForPerfectDodge": "Evasive Fencer",
    "Talent_Fencer_RiposteDamageBonus": "Riposte Mastery",
    "Talent_Fencer_SlashDamage": "Deep Cuts",
    "Talent_Marksman_ActiveReloadSpeedBonus": "Quick Hand",
    "Talent_Marksman_ConsecutiveRangeHitsBonus": "Bulletstorm",
    "Talent_Marksman_DamageForAimingState": "Sniper's Focus",
    "Talent_Marksman_DamageForDistance": "Extended Reach",
    "Talent_Marksman_DamageForPointBlank": "Muzzle Reach",
    "Talent_Marksman_Overpenetration": "Overpenetration",
    "Talent_Marksman_PassiveReloadBonus": "Planning Ahead",
    "Talent_Marksman_PierceDamage": "Deep Impact",
    "Talent_Marksman_RangeCritDamageBonus": "Bull's Eye",
    "Talent_Marksman_RangeDamageBonus": "Firearm Training",
    "Talent_Marksman_ReloadForKill": "Deadly Hunter",
    "Talent_Toughguy_BlockPostureConsumptionBonus": "Flawless Defence",
    "Talent_Toughguy_DamageResistForHP": "Pain Tolerance",
    "Talent_Toughguy_DamageForManyEnemies": "Outnumbered",
    "Talent_Toughguy_ExtraHP": "Stout Frame",
    "Talent_Toughguy_HealEffectiveness": "Stitches and Rum",
    "Talent_Toughguy_MeleeDamageResist": "Just a Flesh Wound",
    "Talent_Toughguy_ResistForManyEnemies": "Outnumbered",
    "Talent_Toughguy_SaveOnLowHP": "Too Angry to Die",
    "Talent_Toughguy_StaminaBonus": "Marathon Runner",
    "Talent_Toughguy_TempHPForDamageRecivedBonus": "You Will Answer for This",
    "Talent_Toughguy_GlobalDamageResist": "Damage Resistance",
}

TALENT_DESCS: dict[str, str] = {
    "Talent_Crusher_Berserk": "For every X Health lost you gain a stack granting bonus Damage.",
    "Talent_Crusher_CrudeDamage": "Increases Crude Damage.",
    "Talent_Crusher_DamageForDeathNearby": "When an enemy dies nearby, gain Melee Damage bonus for a few seconds.",
    "Talent_Crusher_DamageForMultipleTargets": "Hitting multiple enemies grants stacking Damage bonus.",
    "Talent_Crusher_DamageResistWithTwoHandedWpn": "Gain Damage Resistance while wielding a two-handed weapon.",
    "Talent_Crusher_TemporalHPHealBuff": "Attacks are more effective at converting Temporal Health into Health.",
    "Talent_Crusher_TwoHandedDamage": "Increases two-handed weapon Damage.",
    "Talent_Crusher_TwoHandedMeleeCritChance": "Increases Critical Hit Chance with two-handed melee weapons.",
    "Talent_Crusher_TwoHandedStaminaReduced": "Two-handed weapon attacks consume less Stamina.",
    "Talent_Fencer_ConsecutiveMeleeHitsBonus": "Each consecutive hit increases Damage, capped after several hits.",
    "Talent_Fencer_CritChanceForPerfectBlock": "After a Perfect Block, Critical Hit Chance is increased briefly.",
    "Talent_Fencer_DamageForSoloEnemy": "When only one enemy is within 10m, melee attacks deal bonus Damage.",
    "Talent_Fencer_HealForKill": "On enemy kill, restore Health per tick for a few seconds.",
    "Talent_Fencer_LessStaminaForDash": "Dash and Jump consume less Stamina.",
    "Talent_Fencer_OneHandedDamage": "Increases one-handed weapon Damage.",
    "Talent_Fencer_OneHandedMeleeCritChance": "Increases Critical Hit Chance with one-handed melee weapons.",
    "Talent_Fencer_PassiveReloadBoostForPerfectBlock": "Perfect Blocks restore Passive Gun Reload progress.",
    "Talent_Fencer_PassiveReloadBoostForPerfectDodge": "Perfect Dashes restore Passive Gun Reload progress.",
    "Talent_Fencer_RiposteDamageBonus": "Increases Riposte Damage.",
    "Talent_Fencer_SlashDamage": "Increases Slash Damage.",
    "Talent_Marksman_ActiveReloadSpeedBonus": "Improves Active Reload Speed.",
    "Talent_Marksman_ConsecutiveRangeHitsBonus": "Consecutive ranged hits grant stacking Damage bonus to next shot.",
    "Talent_Marksman_DamageForAimingState": "While aiming, gain stacking Damage bonus over time.",
    "Talent_Marksman_DamageForDistance": "Shots deal bonus Damage per 10m between you and the target.",
    "Talent_Marksman_DamageForPointBlank": "Shots deal bonus Damage at close range (below 10m).",
    "Talent_Marksman_Overpenetration": "Shots penetrate enemies, dealing reduced damage after penetrating.",
    "Talent_Marksman_PassiveReloadBonus": "Improves Passive Gun Reload Speed.",
    "Talent_Marksman_PierceDamage": "Increases Pierce Damage.",
    "Talent_Marksman_RangeCritDamageBonus": "Hitting a critical spot deals bonus Damage.",
    "Talent_Marksman_RangeDamageBonus": "Increases Ranged Damage.",
    "Talent_Marksman_ReloadForKill": "Killing an enemy has a chance to instantly reload your weapon.",
    "Talent_Toughguy_BlockPostureConsumptionBonus": "Blocks consume less Posture Points.",
    "Talent_Toughguy_DamageResistForHP": "For every X Health lost, gain a stack granting Damage Resistance.",
    "Talent_Toughguy_DamageForManyEnemies": "When close to two or more enemies, gain Melee Damage bonus.",
    "Talent_Toughguy_ExtraHP": "Increases maximum Health.",
    "Talent_Toughguy_HealEffectiveness": "Gain increased effect from Healing.",
    "Talent_Toughguy_MeleeDamageResist": "Increases melee Damage Resistance.",
    "Talent_Toughguy_ResistForManyEnemies": "When close to two or more enemies, gain Damage Resistance.",
    "Talent_Toughguy_SaveOnLowHP": "When receiving a killing blow, instantly restore Health. Has a cooldown.",
    "Talent_Toughguy_StaminaBonus": "Grants additional Stamina.",
    "Talent_Toughguy_TempHPForDamageRecivedBonus": "Increases Temporal Health gain when taking damage.",
    "Talent_Toughguy_GlobalDamageResist": "Increases overall Damage Resistance.",
}

SKILL_CATEGORIES: dict[str, dict[str, str]] = {
    "Fencer":    {"label": "Fencer   (UP)",    "prefix": "DA_Talent_Fencer_"},
    "Toughguy":  {"label": "Toughguy (LEFT)",  "prefix": "DA_Talent_Toughguy_"},
    "Marksman":  {"label": "Marksman (DOWN)",  "prefix": "DA_Talent_Marksman_"},
    "Crusher":   {"label": "Crusher  (RIGHT)", "prefix": "DA_Talent_Crusher_"},
}

STAT_NAMES: dict[str, str] = {
    "DA_Strength_Stat":  "Strength",
    "DA_Agility_Stat":   "Agility",
    "DA_Precision_Stat": "Precision",
    "DA_Mastery_Stat":   "Mastery",
    "DA_Vitality_Stat":  "Vitality",
    "DA_Endurance_Stat": "Endurance",
}

# Maximum item stack count used by bulk-max operations.
MAX_STACK_COUNT: int = 99_999

# Maps every known ItemType tag to whether it is safe to stack in bulk.
# False = equipment / jewelry / ship / quest / NPC / reputation — do not touch count.
# True  = consumable / ammo / resource / currency — safe to raise count.
ITEM_TYPE_CAN_STACK: dict[str, bool] = {
    "Inventory.ItemType.Ammo.Cannonball":                 True,
    "Inventory.ItemType.Ammo.GunFireProjectile":          True,
    "Inventory.ItemType.Ammo.Gunpowder":                  True,
    "Inventory.ItemType.Armor.Feets":                     False,
    "Inventory.ItemType.Armor.Hands":                     False,
    "Inventory.ItemType.Armor.Head":                      False,
    "Inventory.ItemType.Armor.Legs":                      False,
    "Inventory.ItemType.Armor.Torso":                     False,
    "Inventory.ItemType.Consumable.Bandage":              True,
    "Inventory.ItemType.Consumable.Elixir":               True,
    "Inventory.ItemType.Consumable.Fish":                 True,
    "Inventory.ItemType.Consumable.Food":                 True,
    "Inventory.ItemType.Consumable.Lantern":              False,
    "Inventory.ItemType.Consumable.Lootable":             True,
    "Inventory.ItemType.Consumable.Ship":                 True,
    "Inventory.ItemType.Currency":                        True,
    "Inventory.ItemType.Invisible":                       False,
    "Inventory.ItemType.Invisible.Reputation.Brethren":   False,
    "Inventory.ItemType.Invisible.Reputation.Buccaneers": False,
    "Inventory.ItemType.Invisible.Reputation.Civilians":  False,
    "Inventory.ItemType.Invisible.Reputation.Smugglers":  False,
    "Inventory.ItemType.Jewelry.Backpack":                False,
    "Inventory.ItemType.Jewelry.Necklace":                False,
    "Inventory.ItemType.Jewelry.Ring":                    False,
    "Inventory.ItemType.NPC.AlchemyStation":              False,
    "Inventory.ItemType.NPC.Bonfire.Cook":                False,
    "Inventory.ItemType.NPC.EquipmentStation":            False,
    "Inventory.ItemType.NPC.Millstone":                   False,
    "Inventory.ItemType.NPC.Quest":                       False,
    "Inventory.ItemType.Quest":                           False,
    "Inventory.ItemType.Quest.Notes":                     False,
    "Inventory.ItemType.Quest.Other":                     False,
    "Inventory.ItemType.Quest.Recipe":                    False,
    "Inventory.ItemType.Resource":                        True,
    "Inventory.ItemType.Ship.Customization.Figurehead":   False,
    "Inventory.ItemType.Ship.Customization.Flag":         False,
    "Inventory.ItemType.Ship.Customization.HullColor":    False,
    "Inventory.ItemType.Ship.Customization.Sail":         False,
    "Inventory.ItemType.Ship.Customization.Stern":        False,
    "Inventory.ItemType.Ship.Equipment.Cannon.Big":       False,
    "Inventory.ItemType.Ship.Equipment.Cannon.Small":     False,
    "Inventory.ItemType.Ship.Equipment.Cannon.Universal": False,
    "Inventory.ItemType.Ship.Equipment.CombatOrders":     False,
    "Inventory.ItemType.Ship.Equipment.CrewPower":        False,
    "Inventory.ItemType.Ship.Equipment.Hull":             False,
    "Inventory.ItemType.Ship.Equipment.RiggingType":      False,
    "Inventory.ItemType.Weapon.MainHand":                 False,
    "Inventory.ItemType.Weapon.OffHand":                  False,
    "Inventory.ItemType.Weapon.TwoHands":                 False,
}

# ItemType tags that support a Level attribute (equipment + ship equipment + jewelry).
ITEM_TYPE_CAN_LEVEL: set[str] = {
    "Inventory.ItemType.Armor.Feets",
    "Inventory.ItemType.Armor.Hands",
    "Inventory.ItemType.Armor.Head",
    "Inventory.ItemType.Armor.Legs",
    "Inventory.ItemType.Armor.Torso",
    "Inventory.ItemType.Jewelry.Necklace",
    "Inventory.ItemType.Jewelry.Ring",
    "Inventory.ItemType.Ship.Equipment.Cannon.Big",
    "Inventory.ItemType.Ship.Equipment.Cannon.Small",
    "Inventory.ItemType.Ship.Equipment.Cannon.Universal",
    "Inventory.ItemType.Ship.Equipment.CombatOrders",
    "Inventory.ItemType.Ship.Equipment.CrewPower",
    "Inventory.ItemType.Ship.Equipment.Hull",
    "Inventory.ItemType.Ship.Equipment.RiggingType",
    "Inventory.ItemType.Weapon.MainHand",
    "Inventory.ItemType.Weapon.OffHand",
    "Inventory.ItemType.Weapon.TwoHands",
}

# Rarity system — ordered worst → best.
RARITY_LABELS: list[str] = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
RARITY_VALUE: dict[str, int] = {name: idx for idx, name in enumerate(RARITY_LABELS)}
RARITY_ORDER: dict[str, int] = {"Legendary": 0, "Epic": 1, "Rare": 2, "Uncommon": 3, "Common": 4}
RARITY_COLOR: dict[str, str] = {
    "Legendary": "#f59e0b",
    "Epic":      "#a855f7",
    "Rare":      "#3b82f6",
    "Uncommon":  "#22c55e",
    "Common":    "#9ca3af",
}

# Token lists for the heuristic map/recipe scanner.
MAP_SCAN_TOKENS: tuple[str, ...] = (
    'map', 'fog', 'fow', 'explor', 'discover', 'visited', 'revealed',
    'unlocked', 'known', 'fasttravel', 'fast_travel', 'poi', 'location',
    'marker', 'region', 'island', 'treasuremap',
)
MAP_PROTECTED_TOKENS: tuple[str, ...] = (
    'inventory', 'itemparams', 'itemid', 'attributes', 'talent', 'stat',
    'slot', 'equipment', 'shipcustomization', 'ship.customization',
)
RECIPE_SCAN_TOKENS: tuple[str, ...] = (
    'recipe', 'craft', 'blueprint', 'schematic', 'formula', 'cookbook',
    'alchemy', 'crafting',
)
RECIPE_PROTECTED_TOKENS: tuple[str, ...] = (
    'inventory.modules', 'itemparams', 'itemid', 'attributes',
)

# Keywords used to identify ship items in the inventory.
SHIP_TOKENS: tuple[str, ...] = (
    'ship', 'hull', 'sail', 'cannon', 'rigging', 'rudder', 'anchor',
    'figurehead', 'stern', 'wheel', 'flag',
)
