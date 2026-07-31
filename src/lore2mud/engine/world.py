"""Authoritative in-memory world state."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import Literal

from lore2mud.combat.service import CombatRound, resolve_combat_round
from lore2mud.content.models import (
    AcceptQuestEffect,
    ContentPack,
    CollectItemQuestDefinition,
    DialogueDefinition,
    DialogueEffect,
    GrantExperienceEffect,
    GrantItemEffect,
    MonsterDefeatedQuestDefinition,
    QuestDefinition,
    ReachRoomQuestDefinition,
    SetFlagEffect,
    ShopDefinition,
    ShopListingDefinition,
)
from lore2mud.engine.models import (
    Character,
    DialogueState,
    Monster,
    Player,
    QuestState,
    Room,
)
from lore2mud.inventory.models import EquippedItems, Inventory, Item, ItemStack
from lore2mud.progression.service import LevelGain, grant_experience


class WorldRuleError(ValueError):
    """Raised when a requested game action violates a world rule."""


@dataclass(frozen=True, slots=True)
class QuestOutcome:
    """One deterministic quest completion owned by ``World``."""
    quest_id: str
    quest_name: str
    kind: Literal["monster_defeated", "reach_room", "collect_item"]
    reward_experience: int
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class LootOutcome:
    """One item placed in the room after a monster defeat."""
    item_id: str
    item_name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class TakeOutcome:
    """Result of taking items from a room."""
    item_id: str
    item_name: str
    quantity: int
    quest_outcomes: tuple[QuestOutcome, ...] = ()
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class MoveOutcome:
    """Additive movement result used by the command layer.

    ``World.move()`` intentionally keeps returning ``Room`` for existing callers;
    CLI code uses ``World.move_with_outcome()`` when it needs quest results.
    """

    room: Room
    quest_outcomes: tuple[QuestOutcome, ...] = ()
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class UseOutcome:
    """Result of using a consumable item."""
    item_id: str
    item_name: str
    quantity: int
    healed_amount: int


@dataclass(frozen=True, slots=True)
class DropOutcome:
    """Result of dropping items into the current room."""
    item_id: str
    item_name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class InspectItemOutcome:
    """Read-only details for an item visible to the player."""
    item_id: str
    item_name: str
    description: str


@dataclass(frozen=True, slots=True)
class ExamineItemOutcome:
    """Typed read-only details for a visible item."""

    item_id: str
    item_name: str
    description: str
    kind: Literal["item"] = field(init=False, default="item")


@dataclass(frozen=True, slots=True)
class ExamineMonsterOutcome:
    """Typed read-only details for a monster in the current room."""

    monster_id: str
    monster_name: str
    description: str
    hp: int
    max_hp: int
    kind: Literal["monster"] = field(init=False, default="monster")


@dataclass(frozen=True, slots=True)
class ExamineCharacterOutcome:
    """Typed read-only details for a character in the current room."""

    character_id: str
    character_name: str
    description: str
    kind: Literal["character"] = field(init=False, default="character")


ExamineOutcome = (
    ExamineItemOutcome | ExamineMonsterOutcome | ExamineCharacterOutcome
)


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
    combat_level_gains: tuple[LevelGain, ...] = ()
    quest_outcomes: tuple[QuestOutcome, ...] = ()
    level_gains: tuple[LevelGain, ...] = ()
    loot_item: LootOutcome | None = None


@dataclass(frozen=True, slots=True)
class DialogueOptionSummary:
    """One selectable option in a dialogue node."""
    option_id: str
    text: str


@dataclass(frozen=True, slots=True)
class GrantItemEffectOutcome:
    """Typed outcome for one ``grant_item`` dialogue effect."""

    item_id: str
    item_name: str
    quantity: int
    quest_outcomes: tuple[QuestOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class GrantExperienceEffectOutcome:
    """Typed outcome for one ``grant_experience`` dialogue effect."""

    amount: int
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class AcceptQuestEffectOutcome:
    """Typed outcome for one explicit ``accept_quest`` effect."""

    quest_id: str
    quest_name: str
    quest_outcomes: tuple[QuestOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class SetFlagEffectOutcome:
    """Typed outcome for a World-owned flag upsert."""

    flag_id: str
    old_value: bool | None
    new_value: bool
    changed: bool


DialogueEffectOutcome = (
    GrantItemEffectOutcome
    | GrantExperienceEffectOutcome
    | AcceptQuestEffectOutcome
    | SetFlagEffectOutcome
)


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
    effect_outcomes: tuple[DialogueEffectOutcome, ...] = ()
    quest_outcomes: tuple[QuestOutcome, ...] = ()
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class ShopOutcome:
    """Read-only view of the fixed catalog in the current room."""

    shop_id: str
    shop_name: str
    catalog: tuple[ShopListingDefinition, ...]
    coins: int


@dataclass(frozen=True, slots=True)
class BuyOutcome:
    """One atomic purchase from an immutable fixed-price catalog."""

    shop_id: str
    shop_name: str
    item_id: str
    item_name: str
    quantity: int
    unit_price: int
    total_price: int
    coins: int
    quest_outcomes: tuple[QuestOutcome, ...] = ()
    level_gains: tuple[LevelGain, ...] = ()


@dataclass(frozen=True, slots=True)
class SellOutcome:
    """One atomic sale to an immutable fixed-price catalog."""

    shop_id: str
    shop_name: str
    item_id: str
    item_name: str
    quantity: int
    unit_price: int
    total_price: int
    coins: int


@dataclass(frozen=True, slots=True)
class DialogueEndOutcome:
    """Result of explicitly ending a dialogue via bye."""
    character_id: str
    character_name: str
    dialogue_id: str


@dataclass(frozen=True, slots=True)
class RecoverOutcome:
    """Result of recovering from defeat."""
    start_room_id: str
    room_name: str
    hp: int
    max_hp: int


_DEAD_ERROR = "你已经倒下了。使用 recover 恢复，或 load 读档。"
_STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_quantity(quantity: int) -> None:
    """Reject non-positive-integer quantities at the World layer."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise WorldRuleError("数量必须为正整数。")


@dataclass(slots=True)
class World:
    pack_id: str
    pack_name: str
    pack_version: str
    start_room_id: str
    rooms: dict[str, Room]
    items: dict[str, Item]
    monsters: dict[str, Monster]
    player: Player
    quest_defs: dict[str, QuestDefinition] = field(default_factory=dict)
    quest_states: dict[str, QuestState] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    equipped: EquippedItems = field(default_factory=EquippedItems)
    characters: dict[str, Character] = field(default_factory=dict)
    dialogue_defs: dict[str, DialogueDefinition] = field(default_factory=dict)
    shop_defs: dict[str, ShopDefinition] = field(default_factory=dict)
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
                item_stacks=[
                    ItemStack(item_id=s.item_id, quantity=s.quantity)
                    for s in room.item_stacks
                ],
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
                loot_item=monster.loot_item,
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
                stack_limit=item.stack_limit,
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
            coins=pack.player.coins,
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
            start_room_id=pack.start_room_id,
            rooms=rooms,
            items=items,
            monsters=monsters,
            player=player,
            quest_defs=quest_defs,
            characters=characters,
            dialogue_defs=dialogue_defs,
            shop_defs=dict(pack.shops),
        )
        # A newly accepted quest can already be satisfied in the starting state.
        # There is no command action to render here; ``quests`` exposes the
        # resulting authoritative state.
        world._accept_quests_for_room(pack.start_room_id)
        return world

    def _accept_quests_for_room(
        self, room_id: str
    ) -> tuple[QuestOutcome, ...]:
        """Accept triggered quests, then settle all eligible accepted quests."""
        for quest_id in sorted(self.quest_defs):
            quest_def = self.quest_defs[quest_id]
            if (
                quest_def.trigger_room_id == room_id
                and quest_def.id not in self.quest_states
            ):
                self._record_quest_acceptance(quest_def.id, reject_existing=False)
        return self._settle_eligible_quests()

    def _record_quest_acceptance(
        self, quest_id: str, *, reject_existing: bool
    ) -> bool:
        """Create one accepted quest state through the sole mutation path."""
        if quest_id not in self.quest_defs:
            raise WorldRuleError(f"任务 {quest_id!r} 不存在。")
        if quest_id in self.quest_states:
            if reject_existing:
                raise WorldRuleError(f"任务 {quest_id} 已经接取或完成。")
            return False
        self.quest_states[quest_id] = QuestState(quest_id=quest_id)
        return True

    def _preflight_explicit_quest_acceptance(
        self,
        quest_id: str,
        accepted_quest_ids: set[str],
    ) -> QuestDefinition:
        """Validate one explicit dialogue acceptance without mutating World."""
        if not isinstance(quest_id, str) or not _STABLE_ID_PATTERN.fullmatch(quest_id):
            raise WorldRuleError("任务 ID 必须是稳定 ID。")
        quest_def = self.quest_defs.get(quest_id)
        if quest_def is None:
            raise WorldRuleError(f"任务 {quest_id!r} 不存在。")
        if quest_id in accepted_quest_ids:
            raise WorldRuleError(f"任务 {quest_id} 已经接取或完成。")
        return quest_def

    def accept_quest(self, quest_id: str) -> tuple[QuestOutcome, ...]:
        """Explicitly accept a quest and immediately settle eligible tasks.

        This public World entry deliberately bypasses a definition's trigger room,
        while retaining M3's single state mutation and settlement authority.
        """
        self._require_alive()
        self._preflight_explicit_quest_acceptance(quest_id, set(self.quest_states))
        with self._atomic_mutation():
            self._record_quest_acceptance(quest_id, reject_existing=True)
            return self._settle_eligible_quests()

    def _settle_eligible_quests(self) -> tuple[QuestOutcome, ...]:
        """Award every newly satisfied accepted quest in stable ID order.

        The caller owns an atomic World mutation. Definitions are fully validated
        before World construction, so this method has no user-input failure path.
        """
        candidates: list[tuple[QuestState, QuestDefinition]] = []
        for quest_id in sorted(self.quest_states):
            state = self.quest_states[quest_id]
            if state.completed:
                continue
            quest_def = self.quest_defs[quest_id]
            if self._quest_condition_met(quest_def):
                candidates.append((state, quest_def))

        outcomes: list[QuestOutcome] = []
        for state, quest_def in candidates:
            gains = tuple(grant_experience(self.player, quest_def.reward_experience))
            # ``completed`` means the reward commit has completed successfully.
            state.completed = True
            outcomes.append(
                QuestOutcome(
                    quest_id=quest_def.id,
                    quest_name=quest_def.name,
                    kind=quest_def.kind,
                    reward_experience=quest_def.reward_experience,
                    level_gains=gains,
                )
            )
        return tuple(outcomes)

    def _quest_condition_met(self, quest_def: QuestDefinition) -> bool:
        if isinstance(quest_def, MonsterDefeatedQuestDefinition):
            return not self.monsters[quest_def.target_monster_id].is_alive
        if isinstance(quest_def, ReachRoomQuestDefinition):
            return self.player.room_id == quest_def.target_room_id
        assert isinstance(quest_def, CollectItemQuestDefinition)
        stack = self.player.inventory.find_stack(quest_def.target_item_id)
        return stack is not None and stack.quantity >= quest_def.required_quantity

    @staticmethod
    def _quest_level_gains(
        outcomes: tuple[QuestOutcome, ...],
    ) -> tuple[LevelGain, ...]:
        return tuple(
            gain
            for outcome in outcomes
            for gain in outcome.level_gains
        )

    @contextmanager
    def _atomic_mutation(self) -> Iterator[None]:
        """Rollback all mutable action state if a post-preflight step fails."""
        snapshot = (
            deepcopy(self.rooms),
            deepcopy(self.monsters),
            deepcopy(self.player),
            deepcopy(self.quest_states),
            deepcopy(self.flags),
            deepcopy(self.equipped),
            deepcopy(self.active_dialogue),
        )
        try:
            yield
        except BaseException:
            (
                self.rooms,
                self.monsters,
                self.player,
                self.quest_states,
                self.flags,
                self.equipped,
                self.active_dialogue,
            ) = snapshot
            raise

    @property
    def current_room(self) -> Room:
        return self.rooms[self.player.room_id]

    def _require_alive(self) -> None:
        """Gate: reject all modifying actions when the player is dead."""
        if not self.player.is_alive:
            raise WorldRuleError(_DEAD_ERROR)

    def recover(self) -> RecoverOutcome:
        """Recover a dead player: restore full HP, move to start room, clear dialogue.

        Only callable when HP == 0.
        """
        if self.player.is_alive:
            raise WorldRuleError("你尚未倒下，无需恢复。")
        self.player.room_id = self.start_room_id
        self.player.hp = self.player.max_hp
        self.active_dialogue = None
        return RecoverOutcome(
            start_room_id=self.start_room_id,
            room_name=self.rooms[self.start_room_id].name,
            hp=self.player.hp,
            max_hp=self.player.max_hp,
        )

    def move(self, direction: str) -> Room:
        """Move while preserving the historical ``Room`` return contract."""
        return self.move_with_outcome(direction).room

    def move_with_outcome(self, direction: str) -> MoveOutcome:
        """Move and return additive quest results for the command layer."""
        self._require_alive()
        normalized = direction.casefold()
        exit_def = self.current_room.exits.get(normalized)
        if exit_def is None:
            raise WorldRuleError(f"这里不能向 {direction} 移动。")
        required_item_id = exit_def.required_item_id
        if required_item_id is not None:
            if not self.player.inventory.has_item(required_item_id):
                item = self.items.get(required_item_id)
                item_name = item.name if item is not None else "未知物品"
                raise WorldRuleError(
                    f"向 {direction} 移动需要持有 {item_name} "
                    f"({required_item_id})。"
                )
        with self._atomic_mutation():
            self.player.room_id = exit_def.target_room_id
            self.active_dialogue = None
            quest_outcomes = self._accept_quests_for_room(exit_def.target_room_id)
            return MoveOutcome(
                room=self.current_room,
                quest_outcomes=quest_outcomes,
                level_gains=self._quest_level_gains(quest_outcomes),
            )

    def take(self, item_query: str, quantity: int = 1) -> TakeOutcome:
        self._require_alive()
        _validate_quantity(quantity)
        item_id = self._resolve_stack_id(
            item_query, self.current_room.item_stacks, kind="物品"
        )
        if item_id is None:
            raise WorldRuleError(f"这里没有 {item_query}。")

        src_stack = self.current_room.find_stack(item_id)
        assert src_stack is not None
        if src_stack.quantity < quantity:
            raise WorldRuleError(
                f"数量不足：这里只有 {src_stack.quantity} 个。"
            )

        item = self.items[item_id]
        stack_limit = item.stack_limit
        existing = self.player.inventory.find_stack(item_id)
        if existing is not None:
            if existing.quantity + quantity > stack_limit:
                raise WorldRuleError(f"超过栈上限 ({stack_limit})。")
        else:
            if self.player.inventory.stack_count >= self.player.inventory.capacity:
                raise WorldRuleError("背包已经满了。")

        with self._atomic_mutation():
            src_stack.quantity -= quantity
            if src_stack.quantity == 0:
                self.current_room.item_stacks.remove(src_stack)
            self.player.inventory.add_stack(item_id, quantity)
            quest_outcomes = self._settle_eligible_quests()
            return TakeOutcome(
                item_id=item_id,
                item_name=item.name,
                quantity=quantity,
                quest_outcomes=quest_outcomes,
                level_gains=self._quest_level_gains(quest_outcomes),
            )

    def drop(self, item_query: str, quantity: int = 1) -> DropOutcome:
        """Drop items from inventory into the current room."""
        self._require_alive()
        _validate_quantity(quantity)
        item_id = self._resolve_stack_id(
            item_query, self.player.inventory.stacks, kind="物品"
        )
        if item_id is None:
            raise WorldRuleError("背包中没有该物品。")

        inv_stack = self.player.inventory.find_stack(item_id)
        assert inv_stack is not None
        if inv_stack.quantity < quantity:
            raise WorldRuleError(
                f"数量不足：背包中只有 {inv_stack.quantity} 个。"
            )

        item = self.items[item_id]
        if self.equipped.hand == item_id or self.equipped.body == item_id:
            raise WorldRuleError(f"{item.name} 正在装备中，请先卸下。")

        stack_limit = item.stack_limit
        existing_room = self.current_room.find_stack(item_id)
        if existing_room is not None:
            if existing_room.quantity + quantity > stack_limit:
                raise WorldRuleError(f"超过栈上限 ({stack_limit})。")

        inv_stack.quantity -= quantity
        if inv_stack.quantity == 0:
            self.player.inventory.stacks.remove(inv_stack)
        if existing_room is not None:
            existing_room.quantity += quantity
        else:
            self.current_room.item_stacks.append(
                ItemStack(item_id=item_id, quantity=quantity)
            )
        return DropOutcome(item_id=item_id, item_name=item.name, quantity=quantity)

    def _shop_in_current_room(self) -> ShopDefinition | None:
        """Return the one immutable shop definition for the current room."""
        for shop in self.shop_defs.values():
            if shop.room_id == self.player.room_id:
                return shop
        return None

    def _require_current_shop(self) -> ShopDefinition:
        shop = self._shop_in_current_room()
        if shop is None:
            raise WorldRuleError("当前房间没有商店。")
        return shop

    def _resolve_shop_listing(
        self, shop: ShopDefinition, item_query: str
    ) -> ShopListingDefinition:
        item_id = self._resolve_id_from_ids(
            item_query,
            [listing.item_id for listing in shop.catalog],
            self.items,
            kind="物品",
        )
        if item_id is None:
            raise WorldRuleError(f"{shop.name} 不经营 {item_query}。")
        for listing in shop.catalog:
            if listing.item_id == item_id:
                return listing
        raise AssertionError("已解析的商店物品不在目录中")

    def shop(self) -> ShopOutcome:
        """Inspect the current room's fixed catalog without changing World."""
        shop = self._require_current_shop()
        return ShopOutcome(
            shop_id=shop.id,
            shop_name=shop.name,
            catalog=shop.catalog,
            coins=self.player.coins,
        )

    def buy(self, item_query: str, quantity: int = 1) -> BuyOutcome:
        """Atomically buy from an unlimited, immutable catalog."""
        self._require_alive()
        shop = self._require_current_shop()
        _validate_quantity(quantity)
        listing = self._resolve_shop_listing(shop, item_query)
        item = self.items[listing.item_id]
        total_price = listing.buy_price * quantity

        if self.player.coins < total_price:
            raise WorldRuleError("金币不足。")
        existing = self.player.inventory.find_stack(item.id)
        if item.stack_limit == 1:
            if quantity != 1:
                raise WorldRuleError("stack_limit=1 的物品一次只能购买 1 个。")
            if self._is_item_placed_anywhere(item.id):
                raise WorldRuleError(f"{item.name} 已在世界中，无法重复生成。")
            if self.player.inventory.stack_count >= self.player.inventory.capacity:
                raise WorldRuleError("背包已经满了。")
        elif existing is None:
            if self.player.inventory.stack_count >= self.player.inventory.capacity:
                raise WorldRuleError("背包已经满了。")
            if quantity > item.stack_limit:
                raise WorldRuleError(f"超过栈上限 ({item.stack_limit})。")
        elif existing.quantity + quantity > item.stack_limit:
            raise WorldRuleError(f"超过栈上限 ({item.stack_limit})。")

        with self._atomic_mutation():
            self.player.coins -= total_price
            self.player.inventory.add_stack(item.id, quantity)
            quest_outcomes = self._settle_eligible_quests()
            return BuyOutcome(
                shop_id=shop.id,
                shop_name=shop.name,
                item_id=item.id,
                item_name=item.name,
                quantity=quantity,
                unit_price=listing.buy_price,
                total_price=total_price,
                coins=self.player.coins,
                quest_outcomes=quest_outcomes,
                level_gains=self._quest_level_gains(quest_outcomes),
            )

    def sell(self, item_query: str, quantity: int = 1) -> SellOutcome:
        """Atomically sell one unequipped backpack stack to the fixed catalog."""
        self._require_alive()
        shop = self._require_current_shop()
        _validate_quantity(quantity)
        listing = self._resolve_shop_listing(shop, item_query)
        item = self.items[listing.item_id]
        inv_stack = self.player.inventory.find_stack(item.id)
        if inv_stack is None:
            raise WorldRuleError("背包中没有该物品。")
        if inv_stack.quantity < quantity:
            raise WorldRuleError(
                f"数量不足：背包中只有 {inv_stack.quantity} 个。"
            )
        if self.equipped.hand == item.id or self.equipped.body == item.id:
            raise WorldRuleError(f"{item.name} 正在装备中，请先卸下。")

        total_price = listing.sell_price * quantity
        with self._atomic_mutation():
            self.player.inventory.remove_stack(item.id, quantity)
            self.player.coins += total_price
            return SellOutcome(
                shop_id=shop.id,
                shop_name=shop.name,
                item_id=item.id,
                item_name=item.name,
                quantity=quantity,
                unit_price=listing.sell_price,
                total_price=total_price,
                coins=self.player.coins,
            )

    def _visible_item_ids(self) -> list[str]:
        """Return visible item IDs once, in room-then-inventory order."""
        available: list[str] = []
        seen: set[str] = set()
        for s in self.current_room.item_stacks:
            if s.item_id not in seen:
                available.append(s.item_id)
                seen.add(s.item_id)
        for s in self.player.inventory.stacks:
            if s.item_id not in seen:
                available.append(s.item_id)
                seen.add(s.item_id)
        return available

    def _visible_monster_ids(self) -> list[str]:
        """Return monster IDs currently placed in the player's room."""
        return list(self.current_room.monster_ids)

    def _visible_character_ids(self) -> list[str]:
        """Return character IDs currently placed in the player's room."""
        return [
            character.id
            for character in self.characters.values()
            if character.room_id == self.player.room_id
        ]

    def _build_examine_outcome(
        self,
        target_type: Literal["item", "monster", "character"],
        target_id: str,
    ) -> ExamineOutcome:
        if target_type == "item":
            item = self.items[target_id]
            return ExamineItemOutcome(
                item_id=item.id,
                item_name=item.name,
                description=item.description,
            )
        if target_type == "monster":
            monster = self.monsters[target_id]
            assert monster.hp is not None
            return ExamineMonsterOutcome(
                monster_id=monster.id,
                monster_name=monster.name,
                description=monster.description,
                hp=monster.hp,
                max_hp=monster.max_hp,
            )
        character = self.characters[target_id]
        return ExamineCharacterOutcome(
            character_id=character.id,
            character_name=character.name,
            description=character.description,
        )

    def examine(
        self,
        target_query: str,
        target_type: Literal["item", "monster", "character"] | None = None,
    ) -> ExamineOutcome:
        """Resolve one currently visible entity without changing runtime state.

        An explicit ``target_type`` limits both visibility and ambiguity to that
        branch. Untyped queries prefer an exact stable ID; duplicate exact IDs or
        duplicate names across visible branches require an explicit type.
        """
        normalized = target_query.strip().casefold()
        if not normalized:
            raise WorldRuleError("查看目标不能为空。")

        visible_by_type: dict[
            Literal["item", "monster", "character"],
            tuple[list[str], Mapping[str, object], str, str],
        ] = {
            "item": (
                self._visible_item_ids(),
                self.items,
                "物品",
                f"这里或背包中没有 {target_query}。",
            ),
            "monster": (
                self._visible_monster_ids(),
                self.monsters,
                "怪物",
                f"这里没有怪物 {target_query}。",
            ),
            "character": (
                self._visible_character_ids(),
                self.characters,
                "角色",
                f"这里没有角色 {target_query}。",
            ),
        }

        if target_type is not None:
            if target_type not in visible_by_type:
                raise WorldRuleError(f"查看目标类型无效：{target_type}。")
            available_ids, entities, kind, missing_error = visible_by_type[target_type]
            target_id = self._resolve_id_from_ids(
                target_query, available_ids, entities, kind=kind
            )
            if target_id is None:
                raise WorldRuleError(missing_error)
            return self._build_examine_outcome(target_type, target_id)

        exact_matches: list[tuple[
            Literal["item", "monster", "character"], str
        ]] = []
        for kind, (available_ids, _, _, _) in visible_by_type.items():
            exact_matches.extend(
                (kind, target_id)
                for target_id in available_ids
                if target_id.casefold() == normalized
            )
        if len(exact_matches) == 1:
            return self._build_examine_outcome(*exact_matches[0])
        if len(exact_matches) > 1:
            raise WorldRuleError(
                "目标不唯一，请使用类型限定："
                "examine item|monster|character <目标ID或名称>。"
            )

        name_matches: list[tuple[
            Literal["item", "monster", "character"], str
        ]] = []
        for kind, (available_ids, entities, _, _) in visible_by_type.items():
            name_matches.extend(
                (kind, target_id)
                for target_id in available_ids
                if getattr(entities[target_id], "name", "").casefold() == normalized
            )
        if len(name_matches) == 1:
            return self._build_examine_outcome(*name_matches[0])
        if len(name_matches) > 1:
            matched_types = {kind for kind, _ in name_matches}
            if len(matched_types) == 1:
                labels = {
                    "item": "物品",
                    "monster": "怪物",
                    "character": "角色",
                }
                only_type = next(iter(matched_types))
                raise WorldRuleError(
                    f"{labels[only_type]}名称不唯一，请使用稳定 ID。"
                )
            raise WorldRuleError(
                "目标不唯一，请使用类型限定："
                "examine item|monster|character <目标ID或名称>。"
            )
        raise WorldRuleError(f"这里看不到 {target_query}。")

    def inspect_item(self, item_query: str) -> InspectItemOutcome:
        """Return legacy item-only details for the current room or inventory."""
        outcome = self.examine(item_query, "item")
        assert isinstance(outcome, ExamineItemOutcome)

        return InspectItemOutcome(
            item_id=outcome.item_id,
            item_name=outcome.item_name,
            description=outcome.description,
        )

    def use(self, item_query: str, quantity: int = 1) -> UseOutcome:
        """Use consumable items from the player's inventory."""
        self._require_alive()
        _validate_quantity(quantity)
        item_id = self._resolve_stack_id(
            item_query, self.player.inventory.stacks, kind="物品"
        )
        if item_id is None:
            raise WorldRuleError("背包中没有该物品。")

        inv_stack = self.player.inventory.find_stack(item_id)
        assert inv_stack is not None
        if inv_stack.quantity < quantity:
            raise WorldRuleError(
                f"数量不足：背包中只有 {inv_stack.quantity} 个。"
            )

        item = self.items[item_id]
        if self.equipped.hand == item_id or self.equipped.body == item_id:
            raise WorldRuleError(f"{item.name} 正在装备中，无法使用。")
        if item.heal_amount is None:
            raise WorldRuleError(f"物品 {item.name} 无法使用。")

        current_hp = self.player.hp
        assert current_hp is not None
        missing_hp = self.player.max_hp - current_hp
        if missing_hp <= 0:
            raise WorldRuleError("你已经满血了。")

        actual_heal = min(quantity * item.heal_amount, missing_hp)
        self.player.hp = current_hp + actual_heal
        inv_stack.quantity -= quantity
        if inv_stack.quantity == 0:
            self.player.inventory.stacks.remove(inv_stack)
        return UseOutcome(
            item_id=item_id,
            item_name=item.name,
            quantity=quantity,
            healed_amount=actual_heal,
        )

    def equip(self, item_query: str) -> EquipOutcome:
        """Equip an item from the player's inventory."""
        self._require_alive()
        item_id = self._resolve_stack_id(
            item_query, self.player.inventory.stacks, kind="物品"
        )
        if item_id is None:
            raise WorldRuleError("背包中没有该物品。")

        inv_stack = self.player.inventory.find_stack(item_id)
        assert inv_stack is not None
        if inv_stack.quantity != 1:
            raise WorldRuleError("装备物品数量必须为 1。")

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
        self._require_alive()
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
        self._require_alive()
        monster_id = self._resolve_id_from_ids(
            monster_query,
            self.current_room.monster_ids,
            self.monsters,
            kind="怪物",
        )
        if monster_id is None:
            raise WorldRuleError(f"这里没有可攻击的 {monster_query}。")

        monster = self.monsters[monster_id]

        # Loot preflight BEFORE combat
        if monster.loot_item is not None:
            loot_def = monster.loot_item
            loot_item_id = loot_def.item_id
            loot_qty = loot_def.quantity
            stack_limit = self.items[loot_item_id].stack_limit

            if stack_limit == 1:
                if self._is_item_placed_anywhere(loot_item_id):
                    raise WorldRuleError(
                        f"战利品无法放置：{self.items[loot_item_id].name} 已在世界中。"
                    )
            else:
                existing = self.current_room.find_stack(loot_item_id)
                if existing is not None:
                    if existing.quantity + loot_qty > stack_limit:
                        raise WorldRuleError(
                            f"战利品无法放置：超过栈上限 ({stack_limit})。"
                        )

        with self._atomic_mutation():
            combat = resolve_combat_round(
                self.player, monster,
                player_attack=self.effective_attack,
                player_defense=self.effective_defense,
            )
            combat_level_gains: tuple[LevelGain, ...] = ()
            quest_outcomes: tuple[QuestOutcome, ...] = ()
            loot_outcome: LootOutcome | None = None

            if combat.monster_defeated:
                self.current_room.monster_ids.remove(monster_id)
                combat_level_gains = tuple(
                    grant_experience(self.player, monster.experience_reward)
                )

                if monster.loot_item is not None:
                    loot_def = monster.loot_item
                    loot_item_id = loot_def.item_id
                    loot_qty = loot_def.quantity
                    existing = self.current_room.find_stack(loot_item_id)
                    if existing is not None:
                        existing.quantity += loot_qty
                    else:
                        self.current_room.item_stacks.append(
                            ItemStack(item_id=loot_item_id, quantity=loot_qty)
                        )
                    loot_outcome = LootOutcome(
                        item_id=loot_item_id,
                        item_name=self.items[loot_item_id].name,
                        quantity=loot_qty,
                    )

                quest_outcomes = self._settle_eligible_quests()

            return AttackOutcome(
                combat=combat,
                combat_level_gains=combat_level_gains,
                quest_outcomes=quest_outcomes,
                # Preserve the historical attack-wide aggregate while the
                # command layer renders combat and quest gains in their
                # respective deterministic result paths.
                level_gains=(
                    combat_level_gains
                    + self._quest_level_gains(quest_outcomes)
                ),
                loot_item=loot_outcome,
            )

    def start_dialogue(self, character_query: str) -> TalkOutcome:
        """Start dialogue with a character in the current room."""
        self._require_alive()
        room_char_ids = [
            c.id for c in self.characters.values()
            if c.room_id == self.player.room_id
        ]
        character_id = self._resolve_id_from_ids(
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

    def _preflight_dialogue_effects(
        self, effects: tuple[DialogueEffect, ...]
    ) -> None:
        """Validate a complete ordered effect list without changing World."""
        projected_quantities = {
            stack.item_id: stack.quantity
            for stack in self.player.inventory.stacks
        }
        projected_stack_count = self.player.inventory.stack_count
        projected_quest_ids = set(self.quest_states)

        for effect in effects:
            if isinstance(effect, GrantItemEffect):
                if (
                    not isinstance(effect.item_id, str)
                    or not _STABLE_ID_PATTERN.fullmatch(effect.item_id)
                ):
                    raise WorldRuleError("对话奖励物品 ID 必须是稳定 ID。")
                _validate_quantity(effect.quantity)
                item = self.items.get(effect.item_id)
                if item is None:
                    raise WorldRuleError(
                        f"对话奖励物品 {effect.item_id!r} 不存在。"
                    )
                if item.heal_amount is not None:
                    raise WorldRuleError("对话奖励不能是消耗品。")
                if effect.quantity > item.stack_limit:
                    raise WorldRuleError(f"超过栈上限 ({item.stack_limit})。")

                existing_quantity = projected_quantities.get(item.id)
                if item.stack_limit == 1:
                    if effect.quantity != 1:
                        raise WorldRuleError("stack_limit=1 的对话奖励数量必须为 1。")
                    if (
                        existing_quantity is not None
                        or self._is_item_placed_anywhere(item.id)
                    ):
                        raise WorldRuleError(f"你已经拥有 {item.name}。")
                    if projected_stack_count >= self.player.inventory.capacity:
                        raise WorldRuleError("背包已满，无法获得对话奖励。")
                    projected_quantities[item.id] = 1
                    projected_stack_count += 1
                elif existing_quantity is None:
                    if projected_stack_count >= self.player.inventory.capacity:
                        raise WorldRuleError("背包已满，无法获得对话奖励。")
                    projected_quantities[item.id] = effect.quantity
                    projected_stack_count += 1
                elif existing_quantity + effect.quantity > item.stack_limit:
                    raise WorldRuleError(f"超过栈上限 ({item.stack_limit})。")
                else:
                    projected_quantities[item.id] = (
                        existing_quantity + effect.quantity
                    )
            elif isinstance(effect, GrantExperienceEffect):
                _validate_quantity(effect.amount)
            elif isinstance(effect, AcceptQuestEffect):
                self._preflight_explicit_quest_acceptance(
                    effect.quest_id, projected_quest_ids
                )
                projected_quest_ids.add(effect.quest_id)
            elif isinstance(effect, SetFlagEffect):
                if (
                    not isinstance(effect.flag_id, str)
                    or not _STABLE_ID_PATTERN.fullmatch(effect.flag_id)
                ):
                    raise WorldRuleError("flag ID 必须是稳定 ID。")
                if not isinstance(effect.value, bool):
                    raise WorldRuleError("flag 值必须是布尔值。")
            else:
                raise WorldRuleError("对话效果类型无效。")

    def select_option(self, index: int) -> TalkOutcome:
        """Select an option after preflighting and atomically applying effects."""
        self._require_alive()
        if self.active_dialogue is None:
            raise WorldRuleError("你没有在和任何人对话。")

        dialogue = self.dialogue_defs[self.active_dialogue.dialogue_id]
        node = dialogue.nodes[self.active_dialogue.current_node_id]
        if index < 1 or index > len(node.options):
            raise WorldRuleError(f"无效的选项：{index}。")

        option = node.options[index - 1]
        character = self.characters[dialogue.character_id]
        self._preflight_dialogue_effects(option.effects)

        # Every post-preflight operation, including quest settlement and dialogue
        # advancement, shares one local-memory transaction.
        with self._atomic_mutation():
            effect_outcomes: list[DialogueEffectOutcome] = []
            all_quest_outcomes: list[QuestOutcome] = []
            all_level_gains: list[LevelGain] = []

            for effect in option.effects:
                if isinstance(effect, GrantItemEffect):
                    item = self.items[effect.item_id]
                    self.player.inventory.add_stack(item.id, effect.quantity)
                    quest_outcomes = self._settle_eligible_quests()
                    effect_outcomes.append(
                        GrantItemEffectOutcome(
                            item_id=item.id,
                            item_name=item.name,
                            quantity=effect.quantity,
                            quest_outcomes=quest_outcomes,
                        )
                    )
                    all_quest_outcomes.extend(quest_outcomes)
                    all_level_gains.extend(
                        self._quest_level_gains(quest_outcomes)
                    )
                elif isinstance(effect, GrantExperienceEffect):
                    gains = tuple(grant_experience(self.player, effect.amount))
                    effect_outcomes.append(
                        GrantExperienceEffectOutcome(
                            amount=effect.amount,
                            level_gains=gains,
                        )
                    )
                    all_level_gains.extend(gains)
                elif isinstance(effect, AcceptQuestEffect):
                    quest_def = self.quest_defs[effect.quest_id]
                    self._record_quest_acceptance(
                        effect.quest_id, reject_existing=True
                    )
                    quest_outcomes = self._settle_eligible_quests()
                    effect_outcomes.append(
                        AcceptQuestEffectOutcome(
                            quest_id=quest_def.id,
                            quest_name=quest_def.name,
                            quest_outcomes=quest_outcomes,
                        )
                    )
                    all_quest_outcomes.extend(quest_outcomes)
                    all_level_gains.extend(
                        self._quest_level_gains(quest_outcomes)
                    )
                elif isinstance(effect, SetFlagEffect):
                    old_value = self.flags.get(effect.flag_id)
                    changed = old_value is None or old_value != effect.value
                    if changed:
                        self.flags[effect.flag_id] = effect.value
                    effect_outcomes.append(
                        SetFlagEffectOutcome(
                            flag_id=effect.flag_id,
                            old_value=old_value,
                            new_value=effect.value,
                            changed=changed,
                        )
                    )
                else:
                    raise WorldRuleError("对话效果类型无效。")

            common = {
                "character_id": character.id,
                "character_name": character.name,
                "dialogue_id": dialogue.id,
                "effect_outcomes": tuple(effect_outcomes),
                "quest_outcomes": tuple(all_quest_outcomes),
                "level_gains": tuple(all_level_gains),
            }
            if option.next_node_id is None:
                self.active_dialogue = None
                return TalkOutcome(ended=True, **common)

            next_node = dialogue.nodes[option.next_node_id]
            if next_node.options:
                self.active_dialogue = DialogueState(
                    dialogue_id=dialogue.id,
                    current_node_id=next_node.id,
                )
                return TalkOutcome(
                    node_id=next_node.id,
                    node_text=next_node.text,
                    options=tuple(
                        DialogueOptionSummary(opt.id, opt.text)
                        for opt in next_node.options
                    ),
                    ended=False,
                    **common,
                )

            self.active_dialogue = None
            return TalkOutcome(
                node_id=next_node.id,
                node_text=next_node.text,
                options=(),
                ended=True,
                **common,
            )

    def end_dialogue(self) -> DialogueEndOutcome:
        """Explicitly end the current dialogue."""
        self._require_alive()
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

    def _is_item_placed_anywhere(self, item_id: str) -> bool:
        """Return whether a non-stackable item has any runtime placement."""
        if self.player.inventory.has_item(item_id):
            return True
        return any(
            room.find_stack(item_id) is not None
            for room in self.rooms.values()
        )

    def _resolve_stack_id(
        self,
        query: str,
        stacks: list[ItemStack],
        *,
        kind: str,
    ) -> str | None:
        """Resolve item ID from a list of ItemStack by ID or name."""
        available_ids = [s.item_id for s in stacks]
        return self._resolve_id_from_ids(
            query, available_ids, self.items, kind=kind
        )

    @staticmethod
    def _resolve_id_from_ids(
        query: str,
        available_ids: list[str],
        entities: Mapping[str, object],
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
