"""Authoritative in-memory world state."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Any, Literal

from lore2mud.combat.service import CombatRound, resolve_combat_round
from lore2mud.content.models import (
    AcceptQuestEffect,
    AdjustNarrativeStateEffect,
    AdvanceObjectiveEffect,
    AdvanceSceneEffect,
    CampaignActionDefinition,
    CampaignDefinition,
    CampaignEffect,
    ContentPack,
    CorrectKnowledgeEffect,
    CollectItemQuestDefinition,
    ConditionalText,
    DialogueDefinition,
    DialogueEffect,
    DialogueOption,
    GrantExperienceEffect,
    GrantItemEffect,
    InteractableDefinition,
    MonsterDefeatedQuestDefinition,
    MoveActorEffect,
    QuestDefinition,
    ReachRoomQuestDefinition,
    RemoveItemEffect,
    RetractKnowledgeEffect,
    RevealKnowledgeEffect,
    SceneDefinition,
    SetFlagEffect,
    SetNarrativeStateEffect,
    ShopDefinition,
    ShopListingDefinition,
)
from lore2mud.engine.models import (
    Character,
    DialogueState,
    KnowledgeState,
    Monster,
    ObjectiveState,
    Player,
    QuestState,
    Room,
    SceneState,
)
from lore2mud.inventory.models import EquippedItems, Inventory, Item, ItemStack
from lore2mud.narrative.conditions import evaluate_condition
from lore2mud.narrative.models import (
    ConditionContext,
    NarrativeStateDefinition,
    NarrativeValue,
    QuestStatus,
    narrative_value_is_valid,
)
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
class AvailableCampaignAction:
    """One authoritative action projection with its owning interactable."""

    interactable_id: str
    action: CampaignActionDefinition


@dataclass(frozen=True, slots=True)
class JournalEntry:
    id: str
    category: Literal["story", "objective", "knowledge"]
    title: str
    text: str
    status: str | None = None


@dataclass(frozen=True, slots=True)
class CampaignEffectOutcome:
    kind: str
    target_id: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class CampaignActionOutcome:
    action_id: str
    label: str
    result_text: str
    effect_outcomes: tuple[CampaignEffectOutcome, ...]


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
    narrative_state_defs: dict[str, NarrativeStateDefinition] = field(
        default_factory=dict
    )
    narrative_state: dict[str, NarrativeValue] = field(default_factory=dict)
    equipped: EquippedItems = field(default_factory=EquippedItems)
    characters: dict[str, Character] = field(default_factory=dict)
    dialogue_defs: dict[str, DialogueDefinition] = field(default_factory=dict)
    shop_defs: dict[str, ShopDefinition] = field(default_factory=dict)
    campaign: CampaignDefinition | None = None
    scene_states: dict[str, SceneState] = field(default_factory=dict)
    objective_states: dict[str, ObjectiveState] = field(default_factory=dict)
    knowledge_states: dict[str, KnowledgeState] = field(default_factory=dict)
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
            narrative_state_defs=dict(pack.narrative_state_defs),
            narrative_state={
                state_id: definition.initial
                for state_id, definition in pack.narrative_state_defs.items()
            },
            campaign=pack.campaign,
            scene_states={
                scene_id: SceneState(
                    scene_id=scene_id,
                    status=scene.initial_status,
                    stage_index=0 if scene.initial_status == "active" else None,
                )
                for scene_id, scene in (
                    pack.campaign.scenes.items() if pack.campaign else ()
                )
            },
            objective_states={
                objective_id: ObjectiveState(
                    objective_id=objective_id,
                    status=objective.initial_status,
                )
                for objective_id, objective in (
                    pack.campaign.objectives.items() if pack.campaign else ()
                )
            },
            knowledge_states={
                knowledge_id: KnowledgeState(
                    knowledge_id=knowledge_id,
                    status=knowledge.initial_status,
                )
                for knowledge_id, knowledge in (
                    pack.campaign.knowledge.items() if pack.campaign else ()
                )
            },
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
            deepcopy(self.narrative_state),
            deepcopy(self.equipped),
            deepcopy(self.characters),
            deepcopy(self.scene_states),
            deepcopy(self.objective_states),
            deepcopy(self.knowledge_states),
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
                self.narrative_state,
                self.equipped,
                self.characters,
                self.scene_states,
                self.objective_states,
                self.knowledge_states,
                self.active_dialogue,
            ) = snapshot
            raise

    @property
    def current_room(self) -> Room:
        return self.rooms[self.player.room_id]

    def set_narrative_state(self, state_id: str, value: NarrativeValue) -> None:
        """Set one declared narrative value through the World authority."""
        definition = self.narrative_state_defs.get(state_id)
        if definition is None:
            raise WorldRuleError(f"叙事状态 {state_id!r} 不存在。")
        if not narrative_value_is_valid(definition, value):
            raise WorldRuleError(
                f"叙事状态 {state_id!r} 的值不符合 {definition.kind} 声明。"
            )
        self.narrative_state[state_id] = value

    def condition_context(self) -> ConditionContext:
        """Return a detached, read-only snapshot for pure condition evaluation."""
        inventory_quantities = {
            stack.item_id: stack.quantity
            for stack in self.player.inventory.stacks
        }
        quest_statuses: dict[str, QuestStatus] = {}
        for quest_id in self.quest_defs:
            state = self.quest_states.get(quest_id)
            if state is None:
                quest_statuses[quest_id] = "not_accepted"
            elif state.completed:
                quest_statuses[quest_id] = "completed"
            else:
                quest_statuses[quest_id] = "active"
        return ConditionContext(
            state_values=MappingProxyType(dict(self.narrative_state)),
            inventory_quantities=MappingProxyType(inventory_quantities),
            location_id=self.player.room_id,
            quest_statuses=MappingProxyType(quest_statuses),
        )

    def available_dialogue_options(
        self,
        dialogue_id: str,
        node_id: str,
    ) -> tuple[DialogueOption, ...]:
        """Return the authoritative ordered options available right now."""
        dialogue = self.dialogue_defs[dialogue_id]
        node = dialogue.nodes[node_id]
        context = self.condition_context()
        return tuple(
            option
            for option in node.options
            if option.condition is None
            or evaluate_condition(option.condition, context)
        )

    def _project_text(
        self,
        values: tuple[ConditionalText, ...],
        fallback: str,
    ) -> str:
        context = self.condition_context()
        unconditional = fallback
        for value in values:
            if value.condition is None:
                unconditional = value.text
            elif evaluate_condition(value.condition, context):
                return value.text
        return unconditional

    def location_description(self, location_id: str | None = None) -> str:
        """Project one location description from authoritative state."""
        resolved_id = self.player.room_id if location_id is None else location_id
        room = self.rooms[resolved_id]
        if self.campaign is None:
            return room.description
        view = self.campaign.location_views.get(resolved_id)
        if view is None:
            return room.description
        return self._project_text(view.descriptions, room.description)

    def available_exits(self, location_id: str | None = None) -> dict[str, Any]:
        """Return only exits whose bounded campaign conditions currently pass."""
        resolved_id = self.player.room_id if location_id is None else location_id
        exits = self.rooms[resolved_id].exits
        if self.campaign is None:
            return dict(exits)
        view = self.campaign.location_views.get(resolved_id)
        if view is None:
            return dict(exits)
        context = self.condition_context()
        return {
            direction: exit_definition
            for direction, exit_definition in exits.items()
            if direction not in view.exit_conditions
            or evaluate_condition(view.exit_conditions[direction], context)
        }

    def available_characters(self) -> tuple[Character, ...]:
        """Project actors that are present, enabled, capable, and visible here."""
        context = self.condition_context()
        result: list[Character] = []
        for character in sorted(self.characters.values(), key=lambda value: value.id):
            if (
                character.room_id != self.player.room_id
                or character.presence != "present"
                or not character.enabled
                or character.incapacitated
            ):
                continue
            view = self.campaign.actor_views.get(character.id) if self.campaign else None
            if view is not None and view.condition is not None:
                if not evaluate_condition(view.condition, context):
                    continue
            result.append(character)
        return tuple(result)

    def character_description(self, actor_id: str) -> str:
        character = self.characters[actor_id]
        view = self.campaign.actor_views.get(actor_id) if self.campaign else None
        if view is None:
            return character.description
        return self._project_text(view.descriptions, character.description)

    def dialogue_node_text(self, dialogue_id: str, node_id: str) -> str:
        node = self.dialogue_defs[dialogue_id].nodes[node_id]
        if self.campaign is None:
            return node.text
        dialogue_view = self.campaign.dialogue_views.get(dialogue_id)
        node_view = dialogue_view.nodes.get(node_id) if dialogue_view else None
        if node_view is None:
            return node.text
        return self._project_text(node_view.texts, node.text)

    def available_scenes(self) -> tuple[SceneDefinition, ...]:
        if self.campaign is None:
            return ()
        context = self.condition_context()
        return tuple(
            scene
            for scene_id, scene in sorted(self.campaign.scenes.items())
            if scene.location_id == self.player.room_id
            and self.scene_states[scene_id].status == "active"
            and (
                scene.condition is None
                or evaluate_condition(scene.condition, context)
            )
        )

    def scene_description(self, scene_id: str) -> str:
        if self.campaign is None or scene_id not in self.campaign.scenes:
            raise WorldRuleError(f"场景 {scene_id!r} 不存在。")
        scene = self.campaign.scenes[scene_id]
        state = self.scene_states[scene_id]
        if state.status != "active" or state.stage_index is None:
            raise WorldRuleError(f"场景 {scene_id!r} 当前不可见。")
        return self._project_text(scene.stages[state.stage_index].descriptions, "")

    def available_interactables(self) -> tuple[InteractableDefinition, ...]:
        if self.campaign is None:
            return ()
        context = self.condition_context()
        active_characters = {character.id for character in self.available_characters()}
        active_scene_stages = {}
        for scene in self.available_scenes():
            stage_index = self.scene_states[scene.id].stage_index
            assert stage_index is not None
            active_scene_stages[scene.id] = scene.stages[stage_index]
        result: list[InteractableDefinition] = []
        for interactable in sorted(
            self.campaign.interactables.values(), key=lambda value: value.id
        ):
            if interactable.condition is not None and not evaluate_condition(
                interactable.condition, context
            ):
                continue
            if interactable.scene_id is not None:
                stage = active_scene_stages.get(interactable.scene_id)
                if stage is None or interactable.id not in stage.interactable_ids:
                    continue
            elif interactable.kind == "actor":
                if interactable.target_id not in active_characters:
                    continue
            elif interactable.kind == "location":
                if interactable.target_id != self.player.room_id:
                    continue
            elif interactable.location_id != self.player.room_id:
                continue
            if (
                interactable.kind == "actor"
                and interactable.target_id not in active_characters
            ):
                continue
            result.append(interactable)
        return tuple(result)

    def interactable_description(self, interactable_id: str) -> str:
        if self.campaign is None or interactable_id not in self.campaign.interactables:
            raise WorldRuleError(f"交互对象 {interactable_id!r} 不存在。")
        available_ids = {value.id for value in self.available_interactables()}
        if interactable_id not in available_ids:
            raise WorldRuleError(f"交互对象 {interactable_id!r} 当前不可用。")
        interactable = self.campaign.interactables[interactable_id]
        return self._project_text(interactable.descriptions, "")

    def available_campaign_actions(
        self, interactable_id: str | None = None
    ) -> tuple[AvailableCampaignAction, ...]:
        if self.campaign is None:
            return ()
        context = self.condition_context()
        result: list[AvailableCampaignAction] = []
        for interactable in self.available_interactables():
            if interactable_id is not None and interactable.id != interactable_id:
                continue
            for action_id in interactable.action_ids:
                action = self.campaign.actions[action_id]
                if action.condition is None or evaluate_condition(
                    action.condition, context
                ):
                    result.append(AvailableCampaignAction(interactable.id, action))
        return tuple(result)

    def available_log_entries(self) -> tuple[JournalEntry, ...]:
        if self.campaign is None:
            return ()
        context = self.condition_context()
        result: list[JournalEntry] = []
        for entry in sorted(self.campaign.log_entries.values(), key=lambda value: value.id):
            if entry.condition is not None and not evaluate_condition(entry.condition, context):
                continue
            result.append(
                JournalEntry(
                    id=entry.id,
                    category=entry.category,
                    title=entry.id,
                    text=self._project_text(entry.texts, ""),
                )
            )
        for objective_id, definition in sorted(self.campaign.objectives.items()):
            state = self.objective_states[objective_id]
            if state.status == "inactive":
                continue
            result.append(
                JournalEntry(
                    id=objective_id,
                    category="objective",
                    title=definition.title,
                    text=definition.description,
                    status=state.status,
                )
            )
        for knowledge_id, definition in sorted(self.campaign.knowledge.items()):
            status = self.knowledge_states[knowledge_id].status
            if status == "unknown":
                continue
            result.append(
                JournalEntry(
                    id=knowledge_id,
                    category="knowledge",
                    title=definition.title,
                    text=definition.texts[status],
                    status=status,
                )
            )
        return tuple(result)

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
        exit_def = self.available_exits().get(normalized)
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
        return [character.id for character in self.available_characters()]

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
            description=self.character_description(character.id),
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
        room_char_ids = [character.id for character in self.available_characters()]
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
            options = self.available_dialogue_options(dialogue.id, node.id)
            if not options:
                self.active_dialogue = None
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=node.id,
                node_text=self.dialogue_node_text(dialogue.id, node.id),
                options=tuple(
                    DialogueOptionSummary(opt.id, opt.text)
                    for opt in options
                ),
                ended=not options,
            )

        # End old dialogue if switching
        self.active_dialogue = None

        start_node = dialogue.nodes[dialogue.start_node_id]
        start_options = self.available_dialogue_options(
            dialogue.id, start_node.id
        )
        if start_options:
            self.active_dialogue = DialogueState(
                dialogue_id=dialogue.id,
                current_node_id=start_node.id,
            )
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=start_node.id,
                node_text=self.dialogue_node_text(dialogue.id, start_node.id),
                options=tuple(
                    DialogueOptionSummary(opt.id, opt.text)
                    for opt in start_options
                ),
                ended=False,
            )
        else:
            return TalkOutcome(
                character_id=character.id,
                character_name=character.name,
                dialogue_id=dialogue.id,
                node_id=start_node.id,
                node_text=self.dialogue_node_text(dialogue.id, start_node.id),
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
        available_options = self.available_dialogue_options(
            dialogue.id, node.id
        )
        if index < 1 or index > len(available_options):
            raise WorldRuleError(f"无效的选项：{index}。")

        option = available_options[index - 1]
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
            next_options = self.available_dialogue_options(
                dialogue.id, next_node.id
            )
            if next_options:
                self.active_dialogue = DialogueState(
                    dialogue_id=dialogue.id,
                    current_node_id=next_node.id,
                )
                return TalkOutcome(
                    node_id=next_node.id,
                    node_text=self.dialogue_node_text(dialogue.id, next_node.id),
                    options=tuple(
                        DialogueOptionSummary(opt.id, opt.text)
                        for opt in next_options
                    ),
                    ended=False,
                    **common,
                )

            self.active_dialogue = None
            return TalkOutcome(
                node_id=next_node.id,
                node_text=self.dialogue_node_text(dialogue.id, next_node.id),
                options=(),
                ended=True,
                **common,
            )

    def _apply_campaign_effect(
        self, effect: CampaignEffect
    ) -> CampaignEffectOutcome:
        if isinstance(effect, GrantItemEffect):
            _validate_quantity(effect.quantity)
            item = self.items.get(effect.item_id)
            if item is None:
                raise WorldRuleError(f"物品 {effect.item_id!r} 不存在。")
            existing = self.player.inventory.find_stack(item.id)
            before = existing.quantity if existing else 0
            if effect.quantity > item.stack_limit:
                raise WorldRuleError(f"超过栈上限 ({item.stack_limit})。")
            if item.stack_limit == 1:
                reserved = any(
                    monster.is_alive
                    and monster.loot_item is not None
                    and monster.loot_item.item_id == item.id
                    for monster in self.monsters.values()
                )
                if effect.quantity != 1 or self._is_item_placed_anywhere(item.id) or reserved:
                    raise WorldRuleError(f"物品 {item.name} 已经存在或被其他来源保留。")
            elif existing is not None and existing.quantity + effect.quantity > item.stack_limit:
                raise WorldRuleError(f"超过栈上限 ({item.stack_limit})。")
            if existing is None and self.player.inventory.stack_count >= self.player.inventory.capacity:
                raise WorldRuleError("背包已满，无法获得物品。")
            self.player.inventory.add_stack(item.id, effect.quantity)
            self._settle_eligible_quests()
            return CampaignEffectOutcome(
                effect.kind, item.id, before, before + effect.quantity
            )
        if isinstance(effect, RemoveItemEffect):
            _validate_quantity(effect.quantity)
            item = self.items.get(effect.item_id)
            stack = self.player.inventory.find_stack(effect.item_id)
            if item is None or stack is None or stack.quantity < effect.quantity:
                raise WorldRuleError(f"背包中的物品 {effect.item_id!r} 数量不足。")
            if effect.item_id in {self.equipped.hand, self.equipped.body}:
                raise WorldRuleError(f"物品 {item.name} 已装备，不能移除。")
            before = stack.quantity
            self.player.inventory.remove_stack(effect.item_id, effect.quantity)
            return CampaignEffectOutcome(
                effect.kind, effect.item_id, before, before - effect.quantity
            )
        if isinstance(effect, GrantExperienceEffect):
            _validate_quantity(effect.amount)
            before = self.player.experience
            grant_experience(self.player, effect.amount)
            return CampaignEffectOutcome(
                effect.kind, self.player.id, before, self.player.experience
            )
        if isinstance(effect, AcceptQuestEffect):
            before = effect.quest_id in self.quest_states
            self._preflight_explicit_quest_acceptance(effect.quest_id, set(self.quest_states))
            self._record_quest_acceptance(effect.quest_id, reject_existing=True)
            self._settle_eligible_quests()
            state = self.quest_states[effect.quest_id]
            return CampaignEffectOutcome(
                effect.kind,
                effect.quest_id,
                before,
                "completed" if state.completed else "active",
            )
        if isinstance(effect, SetFlagEffect):
            if not _STABLE_ID_PATTERN.fullmatch(effect.flag_id):
                raise WorldRuleError("flag ID 必须是稳定 ID。")
            if not isinstance(effect.value, bool):
                raise WorldRuleError("flag 值必须是布尔值。")
            before = self.flags.get(effect.flag_id)
            self.flags[effect.flag_id] = effect.value
            return CampaignEffectOutcome(
                effect.kind, effect.flag_id, before, effect.value
            )
        if isinstance(effect, SetNarrativeStateEffect):
            before = self.narrative_state.get(effect.state_id)
            self.set_narrative_state(effect.state_id, effect.value)
            return CampaignEffectOutcome(
                effect.kind, effect.state_id, before, effect.value
            )
        if isinstance(effect, AdjustNarrativeStateEffect):
            before = self.narrative_state.get(effect.state_id)
            if not isinstance(before, int) or isinstance(before, bool):
                raise WorldRuleError(
                    f"叙事状态 {effect.state_id!r} 不是可调整的整数。"
                )
            after = before + effect.amount
            self.set_narrative_state(effect.state_id, after)
            return CampaignEffectOutcome(
                effect.kind, effect.state_id, before, after
            )
        if isinstance(effect, MoveActorEffect):
            actor = self.characters.get(effect.actor_id)
            if actor is None:
                raise WorldRuleError(f"角色 {effect.actor_id!r} 不存在。")
            before = {
                "location_id": actor.room_id,
                "presence": actor.presence,
                "enabled": actor.enabled,
                "incapacitated": actor.incapacitated,
            }
            if effect.location_id is not None:
                if effect.location_id not in self.rooms:
                    raise WorldRuleError(f"房间 {effect.location_id!r} 不存在。")
                actor.room_id = effect.location_id
            if effect.presence is not None:
                actor.presence = effect.presence
            if effect.enabled is not None:
                actor.enabled = effect.enabled
            if effect.incapacitated is not None:
                actor.incapacitated = effect.incapacitated
            if self.active_dialogue is not None:
                dialogue = self.dialogue_defs[self.active_dialogue.dialogue_id]
                if dialogue.character_id == actor.id and actor.id not in {
                    character.id for character in self.available_characters()
                }:
                    self.active_dialogue = None
            after = {
                "location_id": actor.room_id,
                "presence": actor.presence,
                "enabled": actor.enabled,
                "incapacitated": actor.incapacitated,
            }
            return CampaignEffectOutcome(effect.kind, actor.id, before, after)
        if isinstance(effect, AdvanceSceneEffect):
            state = self.scene_states.get(effect.scene_id)
            if state is None or self.campaign is None:
                raise WorldRuleError(f"场景 {effect.scene_id!r} 不存在。")
            scene = self.campaign.scenes[effect.scene_id]
            before = {"status": state.status, "stage_index": state.stage_index}
            if effect.transition == "activate":
                if state.status != "inactive":
                    raise WorldRuleError(f"场景 {effect.scene_id} 不能重复激活。")
                state.status = "active"
                state.stage_index = 0
            elif effect.transition == "advance":
                if state.status != "active" or state.stage_index is None:
                    raise WorldRuleError(f"场景 {effect.scene_id} 尚未激活。")
                if state.stage_index + 1 >= len(scene.stages):
                    raise WorldRuleError(f"场景 {effect.scene_id} 已在最后阶段。")
                state.stage_index += 1
            else:
                if state.status != "active":
                    raise WorldRuleError(f"场景 {effect.scene_id} 尚未激活。")
                state.status = "completed"
                state.stage_index = None
            after = {"status": state.status, "stage_index": state.stage_index}
            return CampaignEffectOutcome(effect.kind, effect.scene_id, before, after)
        if isinstance(effect, AdvanceObjectiveEffect):
            state = self.objective_states.get(effect.objective_id)
            if state is None or self.campaign is None:
                raise WorldRuleError(f"目标 {effect.objective_id!r} 不存在。")
            definition = self.campaign.objectives[effect.objective_id]
            before: Any = state.status
            if effect.transition == "activate":
                if state.status != "inactive":
                    raise WorldRuleError(f"目标 {effect.objective_id} 不能激活。")
                incomplete = [
                    dependency_id
                    for dependency_id in definition.dependency_ids
                    if self.objective_states[dependency_id].status != "completed"
                ]
                if incomplete:
                    raise WorldRuleError(
                        f"目标 {effect.objective_id} 的依赖尚未完成：{incomplete}。"
                    )
                blocked = [
                    exclusive_id
                    for exclusive_id in definition.exclusive_with
                    if self.objective_states[exclusive_id].status
                    in {"active", "in_progress", "completed"}
                ]
                if blocked:
                    raise WorldRuleError(
                        f"目标 {effect.objective_id} 与已选择目标互斥：{blocked}。"
                    )
                state.status = "active"
                for exclusive_id in definition.exclusive_with:
                    other = self.objective_states[exclusive_id]
                    if other.status == "inactive":
                        other.status = "failed"
            elif effect.transition == "start":
                if state.status != "active":
                    raise WorldRuleError(f"目标 {effect.objective_id} 尚未激活。")
                state.status = "in_progress"
            elif effect.transition == "complete":
                if state.status not in {"active", "in_progress"}:
                    raise WorldRuleError(f"目标 {effect.objective_id} 不能完成。")
                state.status = "completed"
            else:
                if state.status not in {"active", "in_progress"}:
                    raise WorldRuleError(f"目标 {effect.objective_id} 不能失败。")
                state.status = "failed"
            return CampaignEffectOutcome(
                effect.kind, effect.objective_id, before, state.status
            )
        if isinstance(effect, RevealKnowledgeEffect):
            state = self.knowledge_states.get(effect.knowledge_id)
            if state is None:
                raise WorldRuleError(f"知识 {effect.knowledge_id!r} 不存在。")
            before = state.status
            rank = {"unknown": 0, "heard": 1, "suspected": 2, "confirmed": 3}
            if before not in rank or rank[effect.status] < rank[before]:
                raise WorldRuleError(
                    f"知识 {effect.knowledge_id} 不能从 {before} 揭示为 {effect.status}。"
                )
            state.status = effect.status
            return CampaignEffectOutcome(
                effect.kind, effect.knowledge_id, before, state.status
            )
        if isinstance(effect, RetractKnowledgeEffect):
            state = self.knowledge_states.get(effect.knowledge_id)
            if state is None or state.status not in {"heard", "suspected", "confirmed"}:
                raise WorldRuleError(f"知识 {effect.knowledge_id} 当前不能撤回。")
            before = state.status
            state.status = "retracted"
            return CampaignEffectOutcome(
                effect.kind, effect.knowledge_id, before, state.status
            )
        if isinstance(effect, CorrectKnowledgeEffect):
            state = self.knowledge_states.get(effect.knowledge_id)
            if state is None or state.status not in {
                "heard",
                "suspected",
                "confirmed",
                "retracted",
            }:
                raise WorldRuleError(f"知识 {effect.knowledge_id} 当前不能修正。")
            before = state.status
            state.status = "corrected"
            return CampaignEffectOutcome(
                effect.kind, effect.knowledge_id, before, state.status
            )
        raise WorldRuleError("campaign effect 类型无效。")

    def _preflight_campaign_effects(
        self, effects: tuple[CampaignEffect, ...]
    ) -> None:
        shadow = deepcopy(self)
        for effect in effects:
            shadow._apply_campaign_effect(effect)

    def execute_campaign_action(self, action_id: str) -> CampaignActionOutcome:
        """Execute one currently projected action by stable ID, atomically."""
        self._require_alive()
        if self.active_dialogue is not None:
            raise WorldRuleError("请先结束当前对话。")
        if not isinstance(action_id, str) or not _STABLE_ID_PATTERN.fullmatch(action_id):
            raise WorldRuleError("动作 ID 必须是稳定 ID。")
        available = {
            projected.action.id: projected.action
            for projected in self.available_campaign_actions()
        }
        action = available.get(action_id)
        if action is None:
            raise WorldRuleError(f"动作 {action_id!r} 当前不可用。")
        self._preflight_campaign_effects(action.effects)
        with self._atomic_mutation():
            outcomes = tuple(
                self._apply_campaign_effect(effect) for effect in action.effects
            )
            return CampaignActionOutcome(
                action.id, action.label, action.result_text, outcomes
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
