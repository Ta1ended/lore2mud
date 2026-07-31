"use strict";

const byId = (id) => document.getElementById(id);
const ui = {
  packName: byId("pack-name"), roomId: byId("room-id"), roomName: byId("room-name"),
  roomDescription: byId("room-description"), aliveState: byId("alive-state"),
  hpValue: byId("hp-value"), hpMeter: byId("hp-meter"), levelValue: byId("level-value"),
  xpValue: byId("xp-value"), attackValue: byId("attack-value"), defenseValue: byId("defense-value"),
  coinValue: byId("coin-value"), inventoryCount: byId("inventory-count"),
  equipmentList: byId("equipment-list"), inventoryList: byId("inventory-list"),
  exitList: byId("exit-list"), encounterList: byId("encounter-list"),
  recoveryPanel: byId("recovery-panel"), recoverButton: byId("recover-button"),
  questCount: byId("quest-count"), questList: byId("quest-list"),
  dialoguePanel: byId("dialogue-panel"), dialogueCharacter: byId("dialogue-character"),
  dialogueText: byId("dialogue-text"), dialogueOptions: byId("dialogue-options"),
  shopPanel: byId("shop-panel"), shopTitle: byId("shop-title"), shopList: byId("shop-list"),
  eventLog: byId("event-log"), toast: byId("toast"), canvas: byId("route-map"),
};

let snapshot = null;
let busy = false;
let toastTimer = null;
const history = [];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(label, action, className = "button") {
  const node = element("button", className, label);
  node.type = "button";
  node.disabled = busy;
  node.addEventListener("click", () => sendAction(action));
  return node;
}

async function fetchSnapshot() {
  const response = await fetch("/api/snapshot", {headers: {Accept: "application/json"}});
  if (!response.ok) throw new Error("无法读取游戏状态。");
  snapshot = await response.json();
  render();
}

async function sendAction(action) {
  if (busy) return;
  busy = true;
  render();
  try {
    const response = await fetch("/api/action", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify(action),
    });
    const result = await response.json();
    snapshot = result.snapshot || snapshot;
    recordEvent(result.event);
    showToast(result.event.message, !result.ok);
  } catch (error) {
    recordEvent({type: "error", message: error.message});
    showToast(error.message, true);
  } finally {
    busy = false;
    render();
  }
}

function showToast(message, isError) {
  window.clearTimeout(toastTimer);
  ui.toast.textContent = message;
  ui.toast.classList.toggle("error", isError);
  ui.toast.hidden = false;
  toastTimer = window.setTimeout(() => { ui.toast.hidden = true; }, 2600);
}

function recordEvent(event) {
  history.unshift({
    type: event.type,
    message: event.message,
    time: new Date().toLocaleTimeString("zh-CN", {hour: "2-digit", minute: "2-digit", second: "2-digit"}),
  });
  if (history.length > 30) history.pop();
}

function render() {
  if (!snapshot) return;
  renderStatus();
  renderRoom();
  renderEquipment();
  renderInventory();
  renderQuests();
  renderDialogue();
  renderShop();
  renderEvents();
  drawRouteMap();
}

function renderStatus() {
  const player = snapshot.player;
  ui.packName.textContent = `${snapshot.pack.name} · ${snapshot.pack.version}`;
  ui.hpValue.textContent = `${player.hp} / ${player.max_hp}`;
  ui.hpMeter.style.width = `${Math.max(0, Math.min(100, player.hp / player.max_hp * 100))}%`;
  ui.hpMeter.style.background = player.hp / player.max_hp <= 0.3 ? "var(--red)" : "var(--green)";
  ui.levelValue.textContent = player.level;
  ui.xpValue.textContent = `${player.experience} / ${player.experience_to_next_level}`;
  ui.attackValue.textContent = player.attack === player.base_attack ? player.attack : `${player.attack} (${player.base_attack})`;
  ui.defenseValue.textContent = player.defense === player.base_defense ? player.defense : `${player.defense} (${player.base_defense})`;
  ui.coinValue.textContent = player.coins;
  ui.inventoryCount.textContent = `${player.inventory_stack_count} / ${player.inventory_capacity}`;
}

function renderRoom() {
  const room = snapshot.room;
  ui.roomId.textContent = room.id;
  ui.roomName.textContent = room.name;
  ui.roomDescription.textContent = room.description;
  ui.aliveState.textContent = snapshot.player.alive ? "状态正常" : "已经倒下";
  ui.aliveState.classList.toggle("dead", !snapshot.player.alive);
  ui.recoveryPanel.hidden = snapshot.player.alive;
  ui.recoverButton.disabled = busy;
  ui.exitList.replaceChildren();
  room.exits.forEach((exit) => {
    const node = button(directionLabel(exit.direction), {type: "move", direction: exit.direction}, `button exit-button${exit.locked ? " locked" : ""}`);
    node.disabled = busy || exit.locked || !snapshot.player.alive;
    node.append(element("span", "", exit.locked ? `需要 ${exit.required_item_name}` : exit.target_room_name));
    ui.exitList.append(node);
  });
  if (!room.exits.length) ui.exitList.append(empty("这里没有出口。"));

  ui.encounterList.replaceChildren();
  room.monsters.forEach((monster) => ui.encounterList.append(entityRow(
    monster.name,
    `${monster.description} 生命 ${monster.hp}/${monster.max_hp}`,
    [button("攻击", {type: "attack", target: monster.id}, "button danger")],
    "hp-inline",
  )));
  room.characters.forEach((character) => ui.encounterList.append(entityRow(
    character.name, character.description,
    [button("交谈", {type: "talk", target: character.id}, "button primary")],
  )));
  room.items.forEach((item) => ui.encounterList.append(entityRow(
    `${item.name} ×${item.quantity}`, item.description,
    [button("拾取", {type: "take", target: item.id})],
  )));
  if (!room.monsters.length && !room.characters.length && !room.items.length) {
    ui.encounterList.append(empty("这里只有雾声与旧设施的回响。"));
  }
}

function directionLabel(direction) {
  const labels = {north: "北行", south: "南行", east: "东行", west: "西行", up: "上行", down: "下行"};
  return labels[direction] || direction;
}

function entityRow(title, description, actions, detailClass = "") {
  const row = element("div", "entity-row");
  const copy = element("div", "entity-copy");
  copy.append(element("strong", detailClass, title), element("p", "", description));
  const controls = element("div", "entity-actions");
  actions.forEach((action) => controls.append(action));
  row.append(copy, controls);
  return row;
}

function renderEquipment() {
  ui.equipmentList.replaceChildren();
  [["hand", "武器"], ["body", "护甲"]].forEach(([slot, label]) => {
    const equipped = snapshot.equipment[slot];
    const row = element("div", "equipment-row");
    row.append(element("span", "", label), element("strong", "", equipped ? equipped.name : "未装备"));
    if (equipped) row.append(button("卸下", {type: "unequip", slot}));
    ui.equipmentList.append(row);
  });
}

function renderInventory() {
  ui.inventoryList.replaceChildren();
  snapshot.inventory.forEach((item) => {
    const row = element("div", "item-row");
    const copy = element("div", "item-copy");
    copy.append(element("strong", "", `${item.name} ×${item.quantity}`));
    const modifiers = [];
    if (item.heal_amount) modifiers.push(`恢复 ${item.heal_amount}`);
    if (item.attack_bonus) modifiers.push(`攻击 +${item.attack_bonus}`);
    if (item.defense_bonus) modifiers.push(`防御 +${item.defense_bonus}`);
    copy.append(element("p", "", item.description));
    if (modifiers.length) copy.append(element("span", "item-meta", modifiers.join(" · ")));
    const actions = element("div", "item-actions");
    if (item.heal_amount) actions.append(button("使用", {type: "use", target: item.id}));
    if (item.slot && !item.equipped) actions.append(button("装备", {type: "equip", target: item.id}));
    if (!item.equipped) actions.append(button("放下", {type: "drop", target: item.id}));
    row.append(copy, actions);
    ui.inventoryList.append(row);
  });
  if (!snapshot.inventory.length) ui.inventoryList.append(empty("背包是空的。"));
}

function renderQuests() {
  ui.questList.replaceChildren();
  ui.questCount.textContent = snapshot.quests.length;
  snapshot.quests.forEach((quest) => {
    const row = element("article", `quest-row ${quest.completed ? "completed" : "active"}`);
    row.append(element("strong", "", quest.name), element("p", "", quest.description));
    const progress = element("div", "quest-progress");
    progress.append(
      element("span", "", quest.completed ? "已完成" : quest.target.name),
      element("span", "", `${quest.target.current}/${quest.target.required} · ${quest.reward_experience} EXP`),
    );
    row.append(progress);
    ui.questList.append(row);
  });
  if (!snapshot.quests.length) ui.questList.append(empty("尚未接取任务。"));
}

function renderDialogue() {
  const dialogue = snapshot.dialogue;
  ui.dialoguePanel.hidden = !dialogue;
  if (!dialogue) return;
  ui.dialogueCharacter.textContent = dialogue.character_name;
  ui.dialogueText.textContent = dialogue.text;
  ui.dialogueOptions.replaceChildren();
  dialogue.options.forEach((option) => {
    ui.dialogueOptions.append(button(`${option.index}. ${option.text}`, {type: "choose_dialogue", index: option.index}, "button primary"));
  });
}

function renderShop() {
  const shop = snapshot.shop;
  ui.shopPanel.hidden = !shop;
  if (!shop) return;
  ui.shopTitle.textContent = shop.name;
  ui.shopList.replaceChildren();
  shop.catalog.forEach((listing) => {
    const row = element("div", "shop-row");
    const copy = element("div", "");
    copy.append(element("strong", "", listing.item_name), element("div", "shop-price", `买 ${listing.buy_price} · 卖 ${listing.sell_price}`));
    const actions = element("div", "entity-actions");
    actions.append(button("购买", {type: "buy", target: listing.item_id}));
    const owned = snapshot.inventory.some((item) => item.id === listing.item_id && !item.equipped);
    const sellButton = button("出售", {type: "sell", target: listing.item_id});
    sellButton.disabled = busy || !owned;
    actions.append(sellButton);
    row.append(copy, actions);
    ui.shopList.append(row);
  });
}

function renderEvents() {
  ui.eventLog.replaceChildren();
  history.forEach((event) => {
    const row = element("li", event.type === "error" ? "error" : "");
    row.append(element("time", "", event.time), document.createTextNode(event.message));
    ui.eventLog.append(row);
  });
  if (!history.length) ui.eventLog.append(empty("行动结果会显示在这里。"));
}

function empty(text) { return element("p", "empty", text); }

function drawRouteMap() {
  const canvas = ui.canvas;
  const bounds = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(320, Math.floor(bounds.width));
  const height = Math.max(160, Math.floor(bounds.height));
  if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
  }
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  const background = context.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, "#0b1615");
  background.addColorStop(0.6, "#17201c");
  background.addColorStop(1, "#16140f");
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "rgba(101,214,209,0.10)";
  context.lineWidth = 1;
  for (let y = 28; y < height; y += 30) {
    context.beginPath();
    context.moveTo(0, y);
    context.bezierCurveTo(width * 0.3, y - 12, width * 0.7, y + 12, width, y - 2);
    context.stroke();
  }
  const center = {x: width / 2, y: height / 2};
  const positions = {
    north: {x: center.x, y: 34}, south: {x: center.x, y: height - 34},
    east: {x: width - 72, y: center.y}, west: {x: 72, y: center.y},
    up: {x: width - 72, y: 34}, down: {x: 72, y: height - 34},
  };
  snapshot.room.exits.forEach((exit, index) => {
    const target = positions[exit.direction] || {x: 72 + index * 86, y: 34};
    context.strokeStyle = exit.locked ? "#9a4f4a" : "#5a8f8b";
    context.lineWidth = 2;
    context.beginPath(); context.moveTo(center.x, center.y); context.lineTo(target.x, target.y); context.stroke();
    context.fillStyle = exit.locked ? "#241514" : "#142725";
    context.strokeStyle = exit.locked ? "#ef766f" : "#65d6d1";
    context.fillRect(target.x - 27, target.y - 16, 54, 32);
    context.strokeRect(target.x - 27, target.y - 16, 54, 32);
    context.fillStyle = "#d9d7cf";
    context.font = "11px Segoe UI, sans-serif";
    context.textAlign = "center";
    context.fillText(directionLabel(exit.direction), target.x, target.y + 4, 48);
  });
  context.fillStyle = "#153c39";
  context.strokeStyle = "#65d6d1";
  context.lineWidth = 2;
  context.fillRect(center.x - 64, center.y - 25, 128, 50);
  context.strokeRect(center.x - 64, center.y - 25, 128, 50);
  context.fillStyle = "#f4f1e8";
  context.font = "600 13px Segoe UI, sans-serif";
  context.textAlign = "center";
  context.fillText(snapshot.room.name, center.x, center.y + 5, 112);
}

byId("save-button").addEventListener("click", () => sendAction({type: "save", slot: normalizedSlot()}));
byId("load-button").addEventListener("click", () => sendAction({type: "load", slot: normalizedSlot()}));
byId("recover-button").addEventListener("click", () => sendAction({type: "recover"}));
byId("end-dialogue").addEventListener("click", () => sendAction({type: "end_dialogue"}));
byId("clear-log").addEventListener("click", () => { history.length = 0; renderEvents(); });
byId("command-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = byId("command-input");
  const command = input.value.trim();
  if (!command) return;
  input.value = "";
  sendAction({type: "command", command});
});

function normalizedSlot() {
  const value = byId("save-slot").value.trim();
  return value === "default" ? null : value;
}

window.addEventListener("resize", () => { if (snapshot) drawRouteMap(); });
fetchSnapshot().catch((error) => showToast(error.message, true));
