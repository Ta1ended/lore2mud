"""Authoritative in-memory world state."""

from __future__ import annotations

from dataclasses import dataclass, field

from lore2mud.combat.service import CombatRound, resolve_combat_round
from lore2mud.content.models import ContentPack, QuestDefinition
from lore2mud.engine.models import Monster, Player, QuestState, Room
from lore2mud.inventory.models import Inventory, Item
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
class AttackOutcome:
    combat: CombatRound
    level_gains: tuple[LevelGain, ...] = ()
    quest_outcome: QuestOutcome | None = None


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
        world = cls(
            pack_id=pack.id,
            pack_name=pack.name,
            pack_version=pack.version,
            rooms=rooms,
            items=items,
            monsters=monsters,
            player=player,
            quest_defs=quest_defs,
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
        combat = resolve_combat_round(self.player, monster)
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
