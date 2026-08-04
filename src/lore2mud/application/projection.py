"""Build the complete player-safe projection for one application turn."""

from __future__ import annotations

from copy import deepcopy
from typing import TypeVar

from lore2mud.application.contracts import (
    AttackIntent,
    BuyIntent,
    CampaignActionIntent,
    CampaignActionView,
    CampaignView,
    CharacterFocusView,
    CharacterView,
    ChooseDialogueIntent,
    DialogueOptionView,
    DialogueView,
    DropIntent,
    EndDialogueIntent,
    EquipIntent,
    EquipmentSlot,
    EquipmentView,
    EquippedItemView,
    ExitView,
    FlagView,
    FocusView,
    GameIntent,
    GameView,
    InteractableKind,
    InteractableView,
    ItemAction,
    ItemFocusView,
    ItemView,
    JournalEntryView,
    JournalCategory,
    KnowledgeStatus,
    MonsterFocusView,
    MonsterView,
    MoveIntent,
    ObjectiveStatus,
    PackView,
    PlayerView,
    QuestTargetView,
    QuestKind,
    QuestView,
    RecoverIntent,
    RoomView,
    SceneStatus,
    SceneView,
    SellIntent,
    ShopListingView,
    ShopAction,
    ShopView,
    TakeIntent,
    TalkIntent,
    UnequipIntent,
    UseIntent,
)
from lore2mud.content.models import (
    CollectItemQuestDefinition,
    MonsterDefeatedQuestDefinition,
    ReachRoomQuestDefinition,
    SceneDefinition,
)
from lore2mud.engine.world import World, WorldRuleError


_IntentT = TypeVar("_IntentT", bound=GameIntent)


def project_game_view(world: World, *, focus: FocusView | None = None) -> GameView:
    """Return a detached, immutable projection with no hidden runtime state."""
    player = world.player
    assert player.hp is not None
    held_ids = player.inventory.all_item_ids

    exits = tuple(
        ExitView(
            direction=direction,
            target_room_id=exit_def.target_room_id,
            target_room_name=world.rooms[exit_def.target_room_id].name,
            required_item_id=exit_def.required_item_id,
            required_item_name=(
                world.items[exit_def.required_item_id].name
                if exit_def.required_item_id is not None
                else None
            ),
            locked=(
                exit_def.required_item_id is not None
                and exit_def.required_item_id not in held_ids
            ),
            move=_available(
                world,
                MoveIntent(direction),
            ),
        )
        for direction, exit_def in sorted(world.available_exits().items())
    )

    # V1 CLI/Web presentation preserves the authored entity order.
    room_items = tuple(
        _item_view(
            world,
            stack.item_id,
            stack.quantity,
            actions=_available_actions(world, (TakeIntent(stack.item_id),)),
        )
        for stack in world.current_room.item_stacks
    )
    inventory = tuple(
        _item_view(
            world,
            stack.item_id,
            stack.quantity,
            actions=_available_actions(
                world,
                (
                    UseIntent(stack.item_id),
                    EquipIntent(stack.item_id),
                    DropIntent(stack.item_id),
                ),
            ),
        )
        for stack in player.inventory.stacks
    )

    monsters = tuple(
        MonsterView(
            id=monster.id,
            name=monster.name,
            description=monster.description,
            hp=_monster_hp(monster.hp),
            max_hp=monster.max_hp,
            attack=monster.attack,
            defense=monster.defense,
            attack_intent=_available(world, AttackIntent(monster.id)),
        )
        for monster_id in world.current_room.monster_ids
        for monster in (world.monsters[monster_id],)
    )
    characters = tuple(
        CharacterView(
            id=character.id,
            name=character.name,
            description=world.character_description(character.id),
            talk=_available(world, TalkIntent(character.id)),
        )
        for character in world.available_characters()
    )

    return GameView(
        pack=PackView(world.pack_id, world.pack_name, world.pack_version),
        player=PlayerView(
            id=player.id,
            name=player.name,
            alive=player.is_alive,
            hp=player.hp,
            max_hp=player.max_hp,
            level=player.level,
            experience=player.experience,
            experience_to_next_level=player.level * 10,
            attack=world.effective_attack,
            base_attack=player.attack,
            defense=world.effective_defense,
            base_defense=player.defense,
            coins=player.coins,
            inventory_capacity=player.inventory.capacity,
            inventory_stack_count=player.inventory.stack_count,
            recover=_available(world, RecoverIntent()),
        ),
        room=RoomView(
            id=world.current_room.id,
            name=world.current_room.name,
            description=world.location_description(),
            exits=exits,
            items=room_items,
            monsters=monsters,
            characters=characters,
            quest_hints=_quest_hints(world),
        ),
        inventory=inventory,
        equipment=EquipmentView(
            hand=_equipped_item(world, EquipmentSlot.HAND),
            body=_equipped_item(world, EquipmentSlot.BODY),
        ),
        quests=_quest_views(world),
        campaign=_campaign_view(world),
        dialogue=_dialogue_view(world),
        shop=_shop_view(world),
        flags=tuple(
            FlagView(flag_id, value)
            for flag_id, value in sorted(world.flags.items())
        ),
        focus=focus,
    )


def _available(world: World, intent: _IntentT) -> _IntentT | None:
    return intent if _probe(world, intent) else None


def _available_actions(
    world: World,
    intents: tuple[_IntentT, ...],
) -> tuple[_IntentT, ...]:
    return tuple(intent for intent in intents if _probe(world, intent))


def _probe(world: World, intent: GameIntent) -> bool:
    """Ask authoritative V1 rules on an isolated clone without exposing a catalog."""
    probe = deepcopy(world)
    try:
        if isinstance(intent, MoveIntent):
            probe.move_with_outcome(intent.direction)
        elif isinstance(intent, TakeIntent):
            probe.take(intent.target, intent.quantity)
        elif isinstance(intent, DropIntent):
            probe.drop(intent.target, intent.quantity)
        elif isinstance(intent, UseIntent):
            probe.use(intent.target, intent.quantity)
        elif isinstance(intent, EquipIntent):
            probe.equip(intent.target)
        elif isinstance(intent, UnequipIntent):
            probe.unequip(intent.slot.value)
        elif isinstance(intent, AttackIntent):
            probe.attack(intent.target)
        elif isinstance(intent, TalkIntent):
            probe.start_dialogue(intent.target)
        elif isinstance(intent, ChooseDialogueIntent):
            probe.select_option(intent.index)
        elif isinstance(intent, EndDialogueIntent):
            probe.end_dialogue()
        elif isinstance(intent, BuyIntent):
            probe.buy(intent.target, intent.quantity)
        elif isinstance(intent, SellIntent):
            probe.sell(intent.target, intent.quantity)
        elif isinstance(intent, CampaignActionIntent):
            probe.execute_campaign_action(intent.action_id)
        elif isinstance(intent, RecoverIntent):
            probe.recover()
        else:
            return False
    except WorldRuleError:
        return False
    return True


def _item_view(
    world: World,
    item_id: str,
    quantity: int,
    *,
    actions: tuple[ItemAction, ...],
) -> ItemView:
    item = world.items[item_id]
    return ItemView(
        id=item.id,
        name=item.name,
        description=item.description,
        quantity=quantity,
        heal_amount=item.heal_amount,
        slot=EquipmentSlot(item.slot) if item.slot is not None else None,
        attack_bonus=item.attack_bonus,
        defense_bonus=item.defense_bonus,
        equipped=item_id in {world.equipped.hand, world.equipped.body},
        actions=actions,
    )


def _equipped_item(world: World, slot: EquipmentSlot) -> EquippedItemView | None:
    item_id = world.equipped.hand if slot is EquipmentSlot.HAND else world.equipped.body
    if item_id is None:
        return None
    item = world.items[item_id]
    intent = UnequipIntent(slot)
    available = _available(world, intent)
    return EquippedItemView(
        id=item.id,
        name=item.name,
        attack_bonus=item.attack_bonus,
        defense_bonus=item.defense_bonus,
        unequip=available if isinstance(available, UnequipIntent) else None,
    )


def _quest_hints(world: World) -> tuple[str, ...]:
    room_id = world.player.room_id
    return tuple(
        f"任务提示：{quest.name} — {quest.description}"
        for quest_id in sorted(world.quest_states)
        for state in (world.quest_states[quest_id],)
        for quest in (world.quest_defs[quest_id],)
        if not state.completed and quest.trigger_room_id == room_id
    )


def _quest_views(world: World) -> tuple[QuestView, ...]:
    result: list[QuestView] = []
    for quest_id in sorted(world.quest_states):
        state = world.quest_states[quest_id]
        quest = world.quest_defs[quest_id]
        if isinstance(quest, MonsterDefeatedQuestDefinition):
            monster = world.monsters[quest.target_monster_id]
            target = QuestTargetView(
                QuestKind(quest.kind),
                monster.id,
                monster.name,
                1 if not monster.is_alive else 0,
                1,
            )
        elif isinstance(quest, ReachRoomQuestDefinition):
            room = world.rooms[quest.target_room_id]
            target = QuestTargetView(
                QuestKind(quest.kind),
                room.id,
                room.name,
                1 if world.player.room_id == room.id else 0,
                1,
            )
        elif isinstance(quest, CollectItemQuestDefinition):
            item = world.items[quest.target_item_id]
            stack = world.player.inventory.find_stack(item.id)
            target = QuestTargetView(
                QuestKind(quest.kind),
                item.id,
                item.name,
                stack.quantity if stack is not None else 0,
                quest.required_quantity,
            )
        else:
            raise AssertionError(f"未知任务定义：{quest!r}")
        result.append(
            QuestView(
                id=quest.id,
                name=quest.name,
                description=quest.description,
                completed=state.completed,
                reward_experience=quest.reward_experience,
                target=target,
            )
        )
    return tuple(result)


def _campaign_view(world: World) -> CampaignView:
    scenes = tuple(
        _scene_view(world, scene)
        for scene in sorted(world.available_scenes(), key=lambda value: value.id)
    )

    actions_by_interactable: dict[str, list[CampaignActionView]] = {}
    for projected in world.available_campaign_actions():
        intent = CampaignActionIntent(projected.action.id)
        available = _available(world, intent)
        if not isinstance(available, CampaignActionIntent):
            continue
        actions_by_interactable.setdefault(projected.interactable_id, []).append(
            CampaignActionView(
                id=projected.action.id,
                label=projected.action.label,
                interactable_id=projected.interactable_id,
                intent=available,
            )
        )

    interactables = tuple(
        InteractableView(
            id=interactable.id,
            name=interactable.name,
            kind=InteractableKind(interactable.kind),
            description=world.interactable_description(interactable.id),
            actions=tuple(actions_by_interactable.get(interactable.id, ())),
        )
        for interactable in sorted(
            world.available_interactables(), key=lambda value: value.id
        )
    )
    actions = tuple(
        action
        for interactable in interactables
        for action in interactable.actions
    )
    journal = tuple(
        JournalEntryView(
            id=entry.id,
            category=JournalCategory(entry.category),
            title=entry.title,
            text=entry.text,
            status=_journal_status(entry.category, entry.status),
        )
        for entry in world.available_log_entries()
    )
    return CampaignView(
        scenes=scenes,
        interactables=interactables,
        actions=actions,
        objectives=tuple(
            entry for entry in journal if entry.category is JournalCategory.OBJECTIVE
        ),
        knowledge=tuple(
            entry for entry in journal if entry.category is JournalCategory.KNOWLEDGE
        ),
        journal=journal,
    )


def _dialogue_view(world: World) -> DialogueView | None:
    active = world.active_dialogue
    if active is None or not world.player.is_alive:
        return None
    dialogue = world.dialogue_defs[active.dialogue_id]
    character = world.characters[dialogue.character_id]
    node = dialogue.nodes[active.current_node_id]
    options: list[DialogueOptionView] = []
    for index, option in enumerate(
        world.available_dialogue_options(dialogue.id, node.id), 1
    ):
        intent = ChooseDialogueIntent(index)
        available = _available(world, intent)
        if isinstance(available, ChooseDialogueIntent):
            options.append(
                DialogueOptionView(
                    index=index,
                    id=option.id,
                    text=option.text,
                    intent=available,
                )
            )
    return DialogueView(
        dialogue_id=dialogue.id,
        character_id=character.id,
        character_name=character.name,
        node_id=node.id,
        text=world.dialogue_node_text(dialogue.id, node.id),
        options=tuple(options),
        end=EndDialogueIntent(),
    )


def _shop_view(world: World) -> ShopView | None:
    shop = next(
        (
            value
            for value in sorted(world.shop_defs.values(), key=lambda value: value.id)
            if value.room_id == world.player.room_id
        ),
        None,
    )
    if shop is None:
        return None
    return ShopView(
        id=shop.id,
        name=shop.name,
        catalog=tuple(
            ShopListingView(
                item_id=listing.item_id,
                item_name=world.items[listing.item_id].name,
                buy_price=listing.buy_price,
                sell_price=listing.sell_price,
                actions=_shop_actions(
                    world,
                    (
                        BuyIntent(listing.item_id),
                        SellIntent(listing.item_id),
                    ),
                ),
            )
            for listing in shop.catalog
        ),
    )


def item_focus(item_id: str, name: str, description: str) -> ItemFocusView:
    return ItemFocusView(item_id, name, description)


def monster_focus(
    monster_id: str,
    name: str,
    description: str,
    hp: int,
    max_hp: int,
) -> MonsterFocusView:
    return MonsterFocusView(monster_id, name, description, hp, max_hp)


def character_focus(
    character_id: str,
    name: str,
    description: str,
) -> CharacterFocusView:
    return CharacterFocusView(character_id, name, description)


def _monster_hp(value: int | None) -> int:
    assert value is not None
    return value


def _scene_view(world: World, scene: SceneDefinition) -> SceneView:
    scene_id = scene.id
    state = world.scene_states[scene_id]
    assert state.stage_index is not None
    return SceneView(
        id=scene_id,
        name=scene.name,
        status=SceneStatus(state.status),
        stage_id=scene.stages[state.stage_index].id,
        description=world.scene_description(scene_id),
    )


def _shop_actions(
    world: World,
    intents: tuple[ShopAction, ...],
) -> tuple[ShopAction, ...]:
    return tuple(intent for intent in intents if _probe(world, intent))


def _journal_status(
    category: str,
    status: str | None,
) -> ObjectiveStatus | KnowledgeStatus | None:
    if status is None:
        return None
    if category == JournalCategory.OBJECTIVE.value:
        return ObjectiveStatus(status)
    if category == JournalCategory.KNOWLEDGE.value:
        return KnowledgeStatus(status)
    raise AssertionError("story journal entries cannot carry a status")
