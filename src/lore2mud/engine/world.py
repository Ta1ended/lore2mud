"""Authoritative in-memory world state."""

from __future__ import annotations

from dataclasses import dataclass, field

from lore2mud.combat.service import CombatRound, resolve_combat_round
from lore2mud.content.models import ContentPack, DialogueDefinition, QuestDefinition
from lore2mud.engine.models import (
    Character,
    DialogueState,
    Monster,
    Player,
    QuestState,
    Room,
)
from lore2mud.inventory.models import EquippedItems, Inventory, Item
from lore2mud.progression.service import LevelGain, grant_experience


class WorldRuleError(ValueError):
    """Raised when a requested game action violates a world rule."""


@dataclass(frozen=True, slots=True)
class QuestOutcome:
    """Result of a quest completion triggered by an attack."""
    quest_id: str
    quest_name: str
    reward_experience: int
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class UseOutcome:
    """Result of using a consumable item."""
    item_id: str
    item_name: str
    healed_amount: int


@dataclass(frozen=True, slots=True)
class EquipOutcome:
    """Result of equipping an item."""
    item_id: str
    item_name: str
    attack_bonus: int = 0
    defense_bonus: int = 0


@dataclass(frozen=True, slots=True)
class UnequipOutcome:
    """Result of unequipping an item."""
    item_id: str
    item_name: str
    attack_bonus: int = 0
    defense_bonus: int = 0


@dataclass(frozen=True, slots=True)
class AttackOutcome:
    combat: CombatRound
    level_gains: tuple[LevelGain, ...] = ()
    quest_outcome: QuestOutcome | None = None


@dataclass(frozen=True, slots=True)
class DialogueOptionSummary:
    """One selectable option in a dialogue node."""
    option_id: str
    text: str


@dataclass(frozen=True, slots=True)
class DialogueItemGrant:
    """One item awarded atomically by a dialogue option."""
    item_id: str
    item_name: str


@dataclass(frozen=True, slots=True)
class TalkOutcome:
    """Result of starting or advancing a dialogue."""
    character_id: str
    character_name: str
    dialogue_id: str
    node_id: str | None = None
    node_text: str | None = None
    options: tuple[DialogueOptionSummary, ...] = ()
    ended: bool = False
    granted_item: DialogueItemGrant | None = None


@dataclass(frozen=True, slots=True)
class DialogueEndOutcome:
    """Result of explicitly ending a dialogue via bye."""
    character_id: str
    character_name: str
    dialogue_id: str


@dataclass(slots=True)
class World:
    pack_id: str
    pack_name: str
    pack_version: str
    rooms: dict[str, Room]
    items: dict[str, Item]
    monsters: dict[str, Monster]
    player: Player
    quest_defs: dict[str, QuestDefinition] = field(default_factory=dict)
    quest_states: dict[str, QuestState] = field(default_factory=dict)
    equipped: EquippedItems = field(default_factory=EquippedItems)
    characters: dict[str, Character] = field(default_factory=dict)
    dialogue_defs: dict[str, DialogueDefinition] = field(default_factory=dict)
    active_dialogue: DialogueState | None = None

    @property
    def effective_attack(self) -> int:
        bonus = 0
        if self.equipped.hand is not None:
            bonus = self.items[self.equipped.hand].attack_bonus
        return self.player.attack + bonus

    @property
    def effective_defense(self) -> int:
        bonus = 0
        if self.equipped.body is not None:
            bonus = self.items[self.equipped.body].defense_bonus
        return self.player.defense + bonus

    @classmethod
    def from_content_pack(
        cls,
        pack: ContentPack,
        *,
        player_name: str = "旅人",
    ) -> "World":
        rooms = {
            room.id: Room(
                id=room.id,
                name=room.name,
                description=room.description,
                exits=dict(room.exits),
                item_ids=list(room.item_ids),
                monster_ids=list(room.monster_ids),
            )
            for room in pack.rooms.values()
        }
        monsters = {
            monster.id: Monster(
                id=monster.id,
                name=monster.name,
                description=monster.description,
                max_hp=monster.max_hp,
                attack=monster.attack,
                defense=monster.defense,
                experience_reward=monster.experience_reward,
            )
            for monster in pack.monsters.values()
        }
        items = {
            item.id: Item(
                id=item.id,
                name=item.name,
                description=item.description,
                heal_amount=item.heal_amount,
                slot=item.slot,
                attack_bonus=item.attack_bonus,
                defense_bonus=item.defense_bonus,
            )
            for item in pack.items.values()
        }
        player = Player(
            id="player_local",
            name=player_name,
            room_id=pack.start_room_id,
            max_hp=pack.player.max_hp,
            attack=pack.player.attack,
            defense=pack.player.defense,
            inventory=Inventory(capacity=pack.player.inventory_capacity),
        )
        quest_defs = dict(pack.quests)
        characters = {
            char_def.id: Character(
                id=char_def.id,
                name=char_def.name,
                description=char_def.description,
                room_id=char_def.room_id,
            )
            for char_def in pack.characters.values()
        }
        dialogue_defs = dict(pack.dialogues)
        world = cls(
            pack_id=pack.id,
            pack_name=pack.name,
            pack_version=pack.version,
            rooms=rooms,
            items=items,
            monsters=monsters,
            player=player,
            quest_defs=quest_defs,
            characters=characters,
            dialogue_defs=dialogue_defs,
        )
        # Auto-accept quests triggered in the start room.
        world._accept_quests_for_room(pack.start_room_id)
        return world

    def _accept_quests_for_room(self, room_id: str) -> None:
        """Accept all quests whose trigger_room_id matches *room_id*."""
        for quest_def in self.quest_defs.values():
            if (
                quest_def.trigger_room_id == room_id
                and quest_def.id not in self.quest_states
            ):
                self.quest_states[quest_def.id] = QuestState(
                    quest_id=quest_def.id,
                )

    @property
    def current_room(self) -> Room:
        return self.rooms[self.player.room_id]

    def move(self, direction: str) -> Room:
        normalized = direction.casefold()
        target_id = self.current_room.exits.get(normalized)
        if target_id is None:
            raise WorldRuleError(f"这里不能向 {direction} 移动。")
        self.player.room_id = target_id
        self._accept_quests_for_room(target_id)
        self.active_dialogue = None
        return self.current_room

    def take(self, item_query: str) -> Item:
        item_id = self._resolve_id(
            item_query,
            self.current_room.item_ids,
            self.items,
            kind="物品",
        )
        if item_id is None:
            raise WorldRuleError(f"这里没有 {item_query}。")
        if not self.player.inventory.can_add:
            raise WorldRuleError("背包已经满了。")

        self.current_room.item_ids.remove(item_id)
        self.player.inventory.add(item_id)
        return self.items[item_id]

    def use(self, item_query: str) -> UseOutcome:
        """Use a consumable item from the player's inventory.

        Raises WorldRuleError for non-usable items, missing items,
        dead player, or full HP.
        """
        # Resolve item from inventory.
        item_id = self._resolve_id(
            item_query,
            self.player.inventory.item_ids,
            self.items,
            kind="物品",
        )
        if item_id is None:
            raise WorldRuleError("背包中没有该物品。")

        item = self.items[item_id]
        if self.equipped.hand == item_id or self.equipped.body == item_id:
            raise WorldRuleError(f"{item.name} 正在装备中，无法使用。")
        if item.heal_amount is None:
            raise WorldRuleError(f"物品 {item.name} 无法使用。")

        if not self.player.is_alive:
            raise WorldRuleError("你已经倒下了，无法使用。")

        missing_hp = self.player.max_hp - self.player.hp
        if missing_hp <= 0:
            raise WorldRuleError("你已经满血了。")

        actual = min(item.heal_amount, missing_hp)
        self.player.hp += actual
        self.player.inventory.item_ids.remove(item_id)
        return UseOutcome(
            item_id=item_id,
            item_name=item.name,
            healed_amount=actual,
        )

    def equip(self, item_query: str) -> EquipOutcome:
        """Equip an item from the player's inventory."""
        item_id = self._resolve_id(
            item_query,
            self.player.inventory.item_ids,
            self.items,
            kind="物品",
        )
        if item_id is None:
            raise WorldRuleError("背包中没有该物品。")

        item = self.items[item_id]

        # Strict tagged-variant validation BEFORE any state change.
        if item.heal_amount is not None:
            raise WorldRuleError(f"物品 {item.name} 无法装备。")
        if item.slot not in ("hand", "body"):
            raise WorldRuleError(f"物品 {item.name} 无法装备。")

        if item.slot == "hand":
            if item.attack_bonus < 1:
                raise WorldRuleError(f"物品 {item.name} 无法装备。")
            if item.defense_bonus != 0:
                raise WorldRuleError(f"物品 {item.name} 无法装备。")
            if self.equipped.hand is not None:
                current = self.items[self.equipped.hand]
                raise WorldRuleError(f"{current.name} 已经装备了。")
        else:  # body
            if item.defense_bonus < 1:
                raise WorldRuleError(f"物品 {item.name} 无法装备。")
            if item.attack_bonus != 0:
                raise WorldRuleError(f"物品 {item.name} 无法装备。")
            if self.equipped.body is not None:
                current = self.items[self.equipped.body]
                raise WorldRuleError(f"{current.name} 已经装备了。")

        # All validation passed — apply state change.
        if item.slot == "hand":
            self.equipped.hand = item_id
        else:
            self.equipped.body = item_id

        return EquipOutcome(
            item_id=item_id,
            item_name=item.name,
            attack_bonus=item.attack_bonus,
            defense_bonus=item.defense_bonus,
        )

    def unequip(self, slot: str = "hand") -> UnequipOutcome:
        """Unequip the item in the specified slot (default: hand)."""
        if slot == "hand":
            if self.equipped.hand is None:
                raise WorldRuleError("hand 没有装备中的物品。")
            item_id = self.equipped.hand
            self.equipped.hand = None
        elif slot == "body":
            if self.equipped.body is None:
                raise WorldRuleError("body 没有装备中的物品。")
            item_id = self.equipped.body
            self.equipped.body = None
        else:
            raise WorldRuleError(f"未知槽位：{slot}")

        item = self.items[item_id]
        return UnequipOutcome(
            item_id=item_id,
            item_name=item.name,
            attack_bonus=item.attack_bonus,
            defense_bonus=item.defense_bonus,
        )

    def attack(self, monster_query: str) -> AttackOutcome:
        monster_id = self._resolve_id(
            monster_query,
            self.current_room.monster_ids,
            self.monsters,
            kind="怪物",
        )
        if monster_id is None:
            raise WorldRuleError(f"这里没有可攻击的 {monster_query}。")
        if not self.player.is_alive:
            raise WorldRuleError("你已经无法继续战斗。")

        monster = self.monsters[monster_id]
        combat = resolve_combat_round(
            self.player, monster,
            player_attack=self.effective_attack,
            player_defense=self.effective_defense,
        )
        level_gains: list[LevelGain] = []
        quest_outcome: QuestOutcome | None = None

        if combat.monster_defeated:
            self.current_room.monster_ids.remove(monster_id)
            level_gains.extend(grant_experience(self.player, monster.experience_reward))

            # Check if this monster completes any accepted quest.
            for qs in self.quest_states.values():
                if qs.completed:
                    continue
                qdef = self.quest_defs.get(qs.quest_id)
                if qdef is None:
                    continue
                if qdef.target_monster_id == monster_id:
                    qs.completed = True
                    quest_level_gains = tuple(
                        grant_experience(self.player, qdef.reward_experience)
                    )
                    level_gains.extend(quest_level_gains)
                    quest_outcome = QuestOutcome(
                        quest_id=qdef.id,
                        quest_name=qdef.name,
                        reward_experience=qdef.reward_experience,
                        level_gains=quest_level_gains,
                    )
                    break  # Only one quest per monster.

        return AttackOutcome(
            combat=combat,
            level_gains=tuple(level_gains),
            quest_outcome=quest_outcome,
        )

    def start_dialogue(self, character_query: str) -> TalkOutcome:
        """Start dialogue with a character in the current room."""
        room_char_ids = [
            c.id for c in self.characters.values()
            if c.room_id == self.player.room_id
        ]
        character_id = self._resolve_id(
            character_query, room_char_ids, self.characters, kind="角色"
        )
        if character_id is None:
            raise WorldRuleError(f"这里没有 {character_query}。")
        character = self.characters[character_id]

        dialogue = self._find_dialogue_for_character(character_id)
        if dialogue is None:
            raise WorldRuleError(f"{character.name} 无话可说。")

        # Re-display if already in this dialogue
        if (
            self.active_dialogue is not None
            and self.active_dialogue.dialogue_id == dialogue.id
        ):
            node = dialogue.nodes[self.active_dialogue.current_node_id]
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=node.id,
                node_text=node.text,
                options=tuple(
                    DialogueOptionSummary(opt.id, opt.text)
                    for opt in node.options
                ),
                ended=False,
            )

        # End old dialogue if switching
        self.active_dialogue = None

        start_node = dialogue.nodes[dialogue.start_node_id]
        if start_node.options:
            self.active_dialogue = DialogueState(
                dialogue_id=dialogue.id,
                current_node_id=start_node.id,
            )
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=start_node.id,
                node_text=start_node.text,
                options=tuple(
                    DialogueOptionSummary(opt.id, opt.text)
                    for opt in start_node.options
                ),
                ended=False,
            )
        else:
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=start_node.id,
                node_text=start_node.text,
                options=(),
                ended=True,
            )

    def select_option(self, index: int) -> TalkOutcome:
        """Select a dialogue option (1-indexed)."""
        if self.active_dialogue is None:
            raise WorldRuleError("你没有在和任何人对话。")

        dialogue = self.dialogue_defs[self.active_dialogue.dialogue_id]
        node = dialogue.nodes[self.active_dialogue.current_node_id]

        if index < 1 or index > len(node.options):
            raise WorldRuleError(f"无效的选项：{index}。")

        option = node.options[index - 1]
        character = self.characters[dialogue.character_id]
        granted_item: DialogueItemGrant | None = None
        if option.grant_item_id is not None:
            item = self.items.get(option.grant_item_id)
            if item is None:
                raise WorldRuleError(
                    f"对话奖励物品 {option.grant_item_id!r} 不存在。"
                )
            if item.heal_amount is not None:
                raise WorldRuleError("对话奖励不能是消耗品。")
            if item.id in self.player.inventory.item_ids:
                raise WorldRuleError(f"你已经拥有 {item.name}。")
            if not self.player.inventory.can_add:
                raise WorldRuleError("背包已满，无法获得对话奖励。")
            granted_item = DialogueItemGrant(item.id, item.name)

        # All reward checks completed; no failure below this line may leave
        # dialogue state changed without also granting the item.
        if granted_item is not None:
            self.player.inventory.add(granted_item.item_id)

        if option.next_node_id is None:
            self.active_dialogue = None
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                ended=True,
                granted_item=granted_item,
            )

        next_node = dialogue.nodes[option.next_node_id]
        if next_node.options:
            self.active_dialogue = DialogueState(
                dialogue_id=dialogue.id,
                current_node_id=next_node.id,
            )
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=next_node.id,
                node_text=next_node.text,
                options=tuple(
                    DialogueOptionSummary(opt.id, opt.text)
                    for opt in next_node.options
                ),
                ended=False,
                granted_item=granted_item,
            )
        else:
            self.active_dialogue = None
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=next_node.id,
                node_text=next_node.text,
                options=(),
                ended=True,
                granted_item=granted_item,
            )

    def end_dialogue(self) -> DialogueEndOutcome:
        """Explicitly end the current dialogue."""
        if self.active_dialogue is None:
            raise WorldRuleError("你没有在和任何人对话。")
        dialogue_id = self.active_dialogue.dialogue_id
        character = self.characters[
            self.dialogue_defs[dialogue_id].character_id
        ]
        self.active_dialogue = None
        return DialogueEndOutcome(
            character_id=character.id,
            character_name=character.name,
            dialogue_id=dialogue_id,
        )

    def _find_dialogue_for_character(
        self, character_id: str
    ) -> DialogueDefinition | None:
        for dialogue in self.dialogue_defs.values():
            if dialogue.character_id == character_id:
                return dialogue
        return None

    @staticmethod
    def _resolve_id(
        query: str,
        available_ids: list[str],
        entities: dict[str, object],
        *,
        kind: str,
    ) -> str | None:
        normalized = query.strip().casefold()
        exact_ids = [
            entity_id
            for entity_id in available_ids
            if entity_id.casefold() == normalized
        ]
        if exact_ids:
            return exact_ids[0]

        name_matches = [
            entity_id
            for entity_id in available_ids
            if getattr(entities[entity_id], "name", "").casefold() == normalized
        ]
        if len(name_matches) > 1:
            raise WorldRuleError(f"{kind}名称不唯一，请使用稳定 ID。")
        return name_matches[0] if name_matches else None
