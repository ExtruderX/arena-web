import math
import random
import json
import os
import sys
import asyncio
import pygame

# --- Web (pygbag) ortam tespiti ---
IS_WEB = (sys.platform == "emscripten")
if IS_WEB:
    # pygbag tarafında JS bridge
    from platform import window
    SAVE_KEY = "arena_save_v7"


# ============================================================
# AYARLAR (İLERDE DÜZENLEMEK İÇİN HER ŞEY BURADA)
# ============================================================

W, H = 960, 540
FPS = 60
SAVE_FILE = os.path.join(os.path.dirname(__file__), "save.json")

# --- Run / Meta ekonomi ---
META_CONVERT_RATE = 0.10     # run skoru * bu oran = meta puan (ölünce/bitince)
META_ROUNDING = "floor"      # "floor" | "round" | "ceil"

# --- Boss ayarları ---
BOSS_EVERY = 35             # her kaç dalgada bir boss
BOSS_ANNOUNCE_TIME = 1.3     # boss başlamadan önce uyarı süresi
BOSS_CLEAR_REWARD_META = 35  # boss kesince meta bonus
BOSS_CLEAR_REWARD_SCORE = 0

# --- Oyuncu ---
PLAYER_RADIUS = 16
PLAYER_MAX_HP_BASE = 150
PLAYER_SPEED_BASE = 260

# --- Mermi / Ateş ---
BULLET_RADIUS = 4
BULLET_SPEED_BASE = 680

# Varsayılan mod (istersen modları da genişletirsin)
DEFAULT_GUN = {
    "fire_cd": 0.10,
    "burst_count": 3,
    "burst_gap": 0.035,
    "multi": 2,
    "spread_deg": 7,
    "damage": 18,
    "bullet_speed": BULLET_SPEED_BASE,
}

# --- Düşman ---
ENEMY_RADIUS = 14
ENEMY_HP_BASE = 30
ENEMY_SPEED_BASE = 110
ENEMY_SPAWN_EVERY_BASE = 0.85
ENEMY_SPAWN_MIN = 0.28

# --- Pickup ---
PICKUP_RADIUS = 10
PICKUP_SPAWN_CHANCE = 0.14

# --- Yetenekler (run içi skor eşiklerine göre açılır) ---
# key: tuş
# unlock_score: bu skora ulaşınca açılır
# cd: cooldown (sn)
# Not: Etkiler de burada değişken.
ABILITIES = {
    "DASH": {
        "key": pygame.K_LSHIFT,
        "unlock_score": 100,
        "cd": 4.0,
        "duration": 0.22,
        "speed_mult": 3,
    },
    "BOMB": {
        "key": pygame.K_q,
        "unlock_score": 150,
        "cd": 7.0,
        "radius": 160,
        "damage": 42,
    },
    "HEAL": {
        "key": pygame.K_e,
        "unlock_score": 150,
        "cd": 9.0,
        "amount": 60,
    },
    "SLOW": {
        "key": pygame.K_f,
        "unlock_score": 250,
        "cd": 12.0,
        "duration": 2.2,
        "enemy_speed_mult": 0.45,
    },
}

# --- Kalıcı Upgradeler (META ile satın alınır) ---
# max_level: sınır
# costs: seviye 1..n maliyetleri
# apply: stat etkisi
UPGRADES = {
    "MAX_HP": {
        "name": "Max HP",
        "max_level": 8,
        "costs": [25, 35, 45, 60, 80, 105, 135, 170],
        "hp_per_level": 8,
    },
    "MOVE_SPEED": {
        "name": "Hareket Hızı",
        "max_level": 8,
        "costs": [20, 28, 38, 52, 70, 92, 118, 148],
        "speed_per_level": 8,
    },
    "DAMAGE": {
        "name": "Hasar",
        "max_level": 10,
        "costs": [30, 42, 58, 78, 105, 140, 185, 245, 320, 410],
        "dmg_per_level": 2,
    },
    "FIRE_RATE": {
        "name": "Ateş Hızı",
        "max_level": 8,
        "costs": [35, 50, 70, 95, 130, 175, 230, 300],
        "fire_cd_mult_per_level": 0.96,  # her level cooldown * 0.96
    },
}


# =========================
# ÖZEL GÜÇLER (MARKET)
# =========================
# Bu güçler META ile kalıcı olarak satın alınır ve her run başında etki eder.
POWERS = {
    "REVIVE": {
        "name": "Tek Can",
        "max_level": 1,
        "costs": [160],
        "desc": "Run basina 1 kez: Olumde %45 HP ile dirilirsin.",
    },
    "START_SHIELD": {
        "name": "Kalkan",
        "max_level": 3,
        "costs": [60, 90, 130],
        "duration": [6.0, 9.0, 12.0],   # run basinda otomatik aktif
        "reduce": 0.5,                  # %50 hasar azaltma
        "desc": "Run basinda otomatik kalkan: hasari %50 azaltir.",
    },
    "MAGNET": {
        "name": "Miknatis",
        "max_level": 3,
        "costs": [45, 75, 110],
        "radius": [120, 180, 240],
        "desc": "Pickup'lari belli yaricapta sana ceker.",
    },
}
# ============================================================
# HARITALAR
# ============================================================

# Haritalar sadece görsel tema + basit engeller (obstacle) getirir.
# Obstacle formatı:
#   ("circle", x, y, r)
#   ("rect", x, y, w, h)

MAPS = [
    {
        "id": "classic",
        "name": "Klasik Arena",
        "desc": "Açık alan, engel yok.",
        "bg": (18, 18, 22),
        "grid": (24, 24, 30),
        "obstacles": [],
    },
    {
        "id": "pillars",
        "name": "Sütunlar",
        "desc": "4 adet dairesel engel, alanı böler.",
        "bg": (16, 18, 20),
        "grid": (23, 25, 30),
        "obstacles": [
            ("circle", int(W*0.25), int(H*0.30), 34),
            ("circle", int(W*0.75), int(H*0.30), 34),
            ("circle", int(W*0.25), int(H*0.70), 34),
            ("circle", int(W*0.75), int(H*0.70), 34),
        ],
    },
    {
        "id": "corridor",
        "name": "Koridor",
        "desc": "Orta bölgeyi daraltan duvarlar.",
        "bg": (17, 17, 21),
        "grid": (24, 24, 31),
        "obstacles": [
            # soldan ve sağdan uzanan iki duvar (ortada geçit bırakır)
            ("rect", 0, int(H*0.40), int(W*0.42), 26),
            ("rect", int(W*0.58), int(H*0.60), int(W*0.42), 26),
        ],
    },
]

async def choose_map(screen, font, big):
    """Maç başında 3 haritadan birini seçtirir. 1/2/3 veya Ok+Enter."""
    clock = pygame.time.Clock()
    selected = 0

    while True:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(MAPS)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(MAPS)
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    idx = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}[event.key]
                    return MAPS[idx]
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return MAPS[selected]

        screen.fill((12, 12, 16))
        t = big.render("HARITA SEC", True, (245, 245, 245))
        screen.blit(t, (W//2 - t.get_width()//2, 60))

        y = 170
        for i, m in enumerate(MAPS):
            col = (255, 235, 180) if i == selected else (220, 220, 220)
            draw_text(screen, font, f"{i+1}) {m['name']}", 120, y, col)
            draw_text(screen, font, f"- {m['desc']}", 140, y + 24, (170, 170, 170))
            y += 74

        draw_text(screen, font, "1/2/3: direkt sec | W/S/Ok: sec | Enter: baslat | ESC: menu", 80, H-60, (170, 170, 170))
        pygame.display.flip()
        await asyncio.sleep(0)

def _resolve_circle_vs_circle(x, y, r, cx, cy, cr):
    """Çember (x,y,r) bir dairesel engelin içine girdiyse dışarı iter."""
    dx, dy = x - cx, y - cy
    d2 = dx*dx + dy*dy
    min_d = r + cr
    if d2 == 0:
        return x + min_d, y, True
    if d2 < min_d*min_d:
        d = math.sqrt(d2)
        nx, ny = dx / d, dy / d
        return cx + nx * min_d, cy + ny * min_d, True
    return x, y, False

def _resolve_circle_vs_rect(x, y, r, rx, ry, rw, rh):
    """Çemberi axis-aligned rect engelin dışına iter."""
    # En yakın nokta
    cx = clamp(x, rx, rx + rw)
    cy = clamp(y, ry, ry + rh)
    dx, dy = x - cx, y - cy
    if dx*dx + dy*dy >= r*r:
        return x, y, False

    # İçeride/temas: en kısa eksenden dışarı it
    # Eğer merkez rect'in içindeyse, çıkış yönünü rect kenarlarına göre seç
    inside = (rx < x < rx+rw) and (ry < y < ry+rh)
    if inside:
        left = abs(x - rx)
        right = abs((rx + rw) - x)
        top = abs(y - ry)
        bottom = abs((ry + rh) - y)
        m = min(left, right, top, bottom)
        if m == left:
            return rx - r, y, True
        if m == right:
            return rx + rw + r, y, True
        if m == top:
            return x, ry - r, True
        return x, ry + rh + r, True
    else:
        # dışarıdan çarpma: normal yönünde it
        if dx == 0 and dy == 0:
            return x + r, y, True
        d = math.hypot(dx, dy)
        nx, ny = dx / d, dy / d
        return cx + nx * r, cy + ny * r, True

def apply_obstacle_collisions(x, y, r, obstacles):
    """Daire şeklindeki entity'yi (player/enemy) engellerle çakışmayacak konuma iter."""
    moved = False
    for ob in obstacles:
        if ob[0] == "circle":
            _, cx, cy, cr = ob
            x, y, did = _resolve_circle_vs_circle(x, y, r, cx, cy, cr)
            moved = moved or did
        else:
            _, rx, ry, rw, rh = ob
            x, y, did = _resolve_circle_vs_rect(x, y, r, rx, ry, rw, rh)
            moved = moved or did
    return x, y, moved

def point_in_obstacles(x, y, obstacles):
    for ob in obstacles:
        if ob[0] == "circle":
            _, cx, cy, cr = ob
            if (x - cx)**2 + (y - cy)**2 <= cr*cr:
                return True
        else:
            _, rx, ry, rw, rh = ob
            if rx <= x <= rx+rw and ry <= y <= ry+rh:
                return True
    return False

def draw_map_background(screen, m):
    screen.fill(m["bg"])
    # Grid
    for gx in range(0, W, 40):
        pygame.draw.line(screen, m["grid"], (gx, 0), (gx, H), 1)
    for gy in range(0, H, 40):
        pygame.draw.line(screen, m["grid"], (0, gy), (W, gy), 1)

def draw_map_obstacles(screen, m):
    # Engelleri çiz
    for ob in m["obstacles"]:
        if ob[0] == "circle":
            _, cx, cy, cr = ob
            pygame.draw.circle(screen, (55, 55, 65), (int(cx), int(cy)), int(cr))
            pygame.draw.circle(screen, (80, 80, 95), (int(cx), int(cy)), int(cr), 2)
        else:
            _, rx, ry, rw, rh = ob
            pygame.draw.rect(screen, (55, 55, 65), (int(rx), int(ry), int(rw), int(rh)))
            pygame.draw.rect(screen, (80, 80, 95), (int(rx), int(ry), int(rw), int(rh)), 2)

# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def vlen(x, y):
    return math.hypot(x, y)

def norm(x, y):
    l = vlen(x, y)
    if l == 0:
        return 0.0, 0.0
    return x / l, y / l

def circle_hit(ax, ay, ar, bx, by, br):
    return (ax - bx) ** 2 + (ay - by) ** 2 <= (ar + br) ** 2

def convert_score_to_meta(score):
    raw = score * META_CONVERT_RATE
    if META_ROUNDING == "round":
        return int(round(raw))
    if META_ROUNDING == "ceil":
        return int(math.ceil(raw))
    return int(math.floor(raw))

def load_save():
    # Web'de (iPad/Safari) dosya sistemi yerine localStorage kullan.
    if IS_WEB:
        try:
            raw = window.localStorage.getItem(SAVE_KEY)
            data = json.loads(raw) if raw else None
        except Exception:
            data = None

        if not isinstance(data, dict):
            data = {"meta": 0, "upgrades": {k: 0 for k in UPGRADES}, "top_scores": [], "powers": {k: 0 for k in POWERS}}

    else:
        if not os.path.exists(SAVE_FILE):
            data = {"meta": 0, "upgrades": {k: 0 for k in UPGRADES}, "top_scores": [], "powers": {k: 0 for k in POWERS}}
        else:
            try:
                with open(SAVE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"meta": 0, "upgrades": {k: 0 for k in UPGRADES}, "top_scores": [], "powers": {k: 0 for k in POWERS}}

    # --- normalize / backwards compatible defaults ---
    if "meta" not in data:
        data["meta"] = 0
    if "upgrades" not in data or not isinstance(data["upgrades"], dict):
        data["upgrades"] = {k: 0 for k in UPGRADES}
    for k in UPGRADES:
        data["upgrades"].setdefault(k, 0)

    if "top_scores" not in data or not isinstance(data["top_scores"], list):
        data["top_scores"] = []
    data["top_scores"] = [int(x) for x in data["top_scores"][:3]]

    if "powers" not in data or not isinstance(data["powers"], dict):
        data["powers"] = {k: 0 for k in POWERS}
    for k in POWERS:
        data["powers"].setdefault(k, 0)

    return data


def save_save(data):
    if IS_WEB:
        try:
            window.localStorage.setItem(SAVE_KEY, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass
        return

    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def update_top_scores(save_data, run_score):
    # En yuksek 3 skor (run skoru) sakla
    try:
        lst = save_data.get("top_scores", [])
        if not isinstance(lst, list):
            lst = []
        lst = [int(x) for x in lst]
        lst.append(int(run_score))
        lst = sorted(lst, reverse=True)[:3]
        save_data["top_scores"] = lst
    except Exception:
        pass

def draw_text(surface, font, text, x, y, col=(240, 240, 240)):
    img = font.render(text, True, col)
    surface.blit(img, (x, y))

# ============================================================
# OYUN NESNELERİ
# ============================================================

class Player:
    def __init__(self, save_data):
        self.x = W * 0.5
        self.y = H * 0.5

        # Kalıcı upgradeleri uygula
        u = save_data["upgrades"]

        self.hp_max = PLAYER_MAX_HP_BASE + u["MAX_HP"] * UPGRADES["MAX_HP"]["hp_per_level"]
        self.hp = self.hp_max

        self.speed_base = PLAYER_SPEED_BASE + u["MOVE_SPEED"] * UPGRADES["MOVE_SPEED"]["speed_per_level"]
        self.speed = self.speed_base

        # Market gucleri uygula
        p = save_data.get("powers", {})
        self.power_levels = p if isinstance(p, dict) else {}
        lvl_sh = int(self.power_levels.get("START_SHIELD", 0) or 0)
        self.shield_time = POWERS["START_SHIELD"]["duration"][lvl_sh-1] if lvl_sh > 0 else 0.0
        self.shield_reduce = POWERS["START_SHIELD"]["reduce"] if lvl_sh > 0 else 0.0

        self.revive_ready = int(self.power_levels.get("REVIVE", 0) or 0) > 0
        lvl_mag = int(self.power_levels.get("MAGNET", 0) or 0)
        self.magnet_radius = POWERS["MAGNET"]["radius"][lvl_mag-1] if lvl_mag > 0 else 0

        # Silah parametreleri
        self.fire_cd = DEFAULT_GUN["fire_cd"]
        # FIRE_RATE upgrade: cooldown çarpanı
        mult = (UPGRADES["FIRE_RATE"]["fire_cd_mult_per_level"] ** u["FIRE_RATE"])
        self.fire_cd *= mult

        self.burst_count = DEFAULT_GUN["burst_count"]
        self.burst_gap = DEFAULT_GUN["burst_gap"]
        self.multi = DEFAULT_GUN["multi"]
        self.spread_deg = DEFAULT_GUN["spread_deg"]
        self.damage = DEFAULT_GUN["damage"] + u["DAMAGE"] * UPGRADES["DAMAGE"]["dmg_per_level"]
        self.bullet_speed = DEFAULT_GUN["bullet_speed"]

        # Durum
        self.score = 0
        self.dead = False
        self.hurt_cd = 0.0  # collision invulnerability timer

        # Ateş state
        self.fire_cd_timer = 0.0
        self.burst_left = 0
        self.burst_timer = 0.0

        # Yetenek state
        self.ability_cd = {name: 0.0 for name in ABILITIES}
        self.dash_timer = 0.0
        self.slow_timer = 0.0

    def unlocked(self, ability_name):
        return self.score >= ABILITIES[ability_name]["unlock_score"]


    def take_damage(self, amount):
        # Kalkan indirimi
        dmg = float(amount)
        if self.shield_time > 0.0 and self.shield_reduce > 0.0:
            dmg = math.ceil(dmg * (1.0 - self.shield_reduce))
        dmg = int(max(1, dmg))
        self.hp = max(0, self.hp - dmg)

        # Tek can (revive)
        if self.hp <= 0 and self.revive_ready:
            self.revive_ready = False
            self.hp = max(1, int(self.hp_max * 0.45))
            self.hurt_cd = max(self.hurt_cd, 1.5)
            # revive aninda kisa kalkan
            self.shield_time = max(self.shield_time, 1.8)


class Bullet:
    def __init__(self, x, y, vx, vy, dmg):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r = BULLET_RADIUS
        self.dmg = dmg

class Hazard:
    # kind: "shot" (küre)
    def __init__(self, x, y, vx, vy, dmg, r=6):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.dmg = dmg
        self.r = r


class Enemy:
    def __init__(self, x, y, speed, hp, radius=ENEMY_RADIUS, is_boss=False):
        self.x, self.y = x, y
        self.speed = speed
        self.hp = hp
        self.hp_max = hp
        self.r = radius
        self.is_boss = is_boss
        if self.is_boss:
            # Boss ekstra davranışlar
            self.tired_timer = 0.0
            self.laser_state = "idle"   # idle|charge|fire
            self.laser_timer = 0.0
            self.laser_dir = (0.0, 1.0)
            self.laser_angle = math.pi/2
            self.laser_spin = 2.6  # rad/s, lazer atışında kendi etrafında dönecek
            self.laser_tick = 0.0  # laser damage tick timer
            self.next_attack_in = 2.5
            self.parts = []
            for i in range(4):
                self.parts.append({
                    "angle": i * (math.tau / 4),
                    "dist": 62,
                    "hp": 70,
                    "r": 12,
                    "shot_cd": random.uniform(1.2, 1.7),
                })

class Pickup:
    # kind: "heal" / "power" / "spd"
    def __init__(self, x, y, kind):
        self.x, self.y = x, y
        self.kind = kind
        self.r = PICKUP_RADIUS

# ============================================================
# SPAWN / SİLAH / YETENEK
# ============================================================

def spawn_enemy(wave):
    side = random.randint(0, 3)
    if side == 0:
        x, y = -30, random.uniform(0, H)
    elif side == 1:
        x, y = W + 30, random.uniform(0, H)
    elif side == 2:
        x, y = random.uniform(0, W), -30
    else:
        x, y = random.uniform(0, W), H + 30

    speed = ENEMY_SPEED_BASE + wave * 6 + random.uniform(-10, 20)
    hp = ENEMY_HP_BASE + wave * 2
    return Enemy(x, y, speed, hp)

def spawn_boss(wave):
    # Boss: daha büyük, daha tank, biraz daha hızlı
    # Değişken yapmak için burada formüller tek yerde.
    radius = 38
    hp = 1400 + wave * 22
    speed = 105 + wave * 1.2
    # Boss'u üstten getir
    x, y = random.uniform(W * 0.2, W * 0.8), -60
    return Enemy(x, y, speed, hp, radius=radius, is_boss=True)

def make_shot_bullets(player, mx, my):
    dx, dy = mx - player.x, my - player.y
    base = math.atan2(dy, dx)

    n = max(1, int(player.multi))
    spread = math.radians(max(0, player.spread_deg))

    if n == 1:
        angles = [base]
    else:
        offsets = [i - (n - 1) / 2 for i in range(n)]
        step = spread / max(1, (n - 1))
        angles = [base + o * step for o in offsets]

    out = []
    for ang in angles:
        vx = math.cos(ang) * player.bullet_speed
        vy = math.sin(ang) * player.bullet_speed
        out.append(Bullet(player.x, player.y, vx, vy, player.damage))
    return out

def ability_try_use(player, ability_name, enemies, effects):
    a = ABILITIES[ability_name]
    if not player.unlocked(ability_name):
        return enemies, effects
    if player.ability_cd[ability_name] > 0:
        return enemies, effects

    # Kullanıldı → cooldown başlat
    player.ability_cd[ability_name] = a["cd"]

    if ability_name == "DASH":
        player.dash_timer = a["duration"]

    elif ability_name == "BOMB":
        cx, cy = player.x, player.y
        rad = a["radius"]
        dmg = a["damage"]
        # Görsel halka efekti
        effects.append(("bomb", cx, cy, rad, 0.18))
        # Alan hasarı
        for e in enemies:
            dx, dy = e.x - cx, e.y - cy
            if dx*dx + dy*dy <= rad*rad:
                e.hp -= dmg
        enemies = [e for e in enemies if e.hp > 0]

    elif ability_name == "HEAL":
        amt = a["amount"]
        player.hp = min(player.hp_max, player.hp + amt)
        effects.append(("heal", player.x, player.y, 0, 0.25))

    elif ability_name == "SLOW":
        player.slow_timer = a["duration"]
        effects.append(("slow", player.x, player.y, 0, a["duration"]))

    return enemies, effects

# ============================================================
# MENÜ / UPGRADE EKRANI
# ============================================================


async def menu_market(screen, font, big, save_data):
    clock = pygame.time.Clock()
    keys = list(POWERS.keys())
    selected = 0

    def can_buy(pw_key):
        lvl = int(save_data["powers"].get(pw_key, 0))
        pw = POWERS[pw_key]
        if lvl >= pw["max_level"]:
            return False, None
        cost = pw["costs"][lvl]
        return save_data["meta"] >= cost, cost

    while True:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "back"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(keys)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(keys)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    k = keys[selected]
                    ok, cost = can_buy(k)
                    if ok and cost is not None:
                        save_data["meta"] -= cost
                        save_data["powers"][k] = int(save_data["powers"].get(k, 0)) + 1
                        save_save(save_data)

        screen.fill((12, 12, 16))
        title = big.render("MARKET", True, (245, 245, 245))
        screen.blit(title, (W//2 - title.get_width()//2, 55))
        draw_text(screen, font, f"META: {save_data['meta']}", 80, 120, (220, 220, 220))

        y = 175
        for i, k in enumerate(keys):
            pw = POWERS[k]
            lvl = int(save_data["powers"].get(k, 0))
            ok, cost = can_buy(k)
            col = (255, 235, 180) if i == selected else (220, 220, 220)

            suffix = ""
            if lvl >= pw["max_level"]:
                suffix = " (MAX)"
            else:
                suffix = f" (Lv {lvl}/{pw['max_level']})  Cost: {cost}"

            draw_text(screen, font, f"{pw['name']}{suffix}", 90, y, col)
            draw_text(screen, font, pw.get("desc",""), 110, y+22, (170, 170, 170))
            y += 58

        draw_text(screen, font, "W/S veya Ok: sec | Enter: satin al | ESC: geri", 80, H-60, (170, 170, 170))
        pygame.display.flip()
        await asyncio.sleep(0)

async def menu_main(screen, font, big, save_data):
    clock = pygame.time.Clock()
    selected = 0
    items = ["RUN BASLAT", "UPGRADE", "MARKET", "CIKIS"]

    while True:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(items)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(items)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return ["start", "upgrade", "market", "quit"][selected]

        screen.fill((15, 15, 19))

        title = big.render("ARENA", True, (245, 245, 245))
        screen.blit(title, (W//2 - title.get_width()//2, 70))

        draw_text(screen, font, f"META: {save_data['meta']}   (save: {'localStorage' if IS_WEB else SAVE_FILE})", 80, 140, (200, 200, 200))
        # Top 3 skor kutusu
        box_x, box_y, box_w, box_h = W - 320, 150, 250, 140
        pygame.draw.rect(screen, (30, 55, 85), (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(screen, (90, 140, 190), (box_x, box_y, box_w, box_h), width=2, border_radius=10)
        draw_text(screen, font, "TOP 3 SKOR", box_x + 20, box_y + 18, (235, 235, 235))
        top = save_data.get("top_scores", [])
        for i in range(3):
            val = top[i] if i < len(top) else 0
            draw_text(screen, font, f"{i+1}) {val}", box_x + 26, box_y + 52 + i*28, (255, 235, 180))


        y = 210
        for i, it in enumerate(items):
            col = (255, 235, 180) if i == selected else (220, 220, 220)
            draw_text(screen, font, it, 120, y, col)
            y += 48

        draw_text(screen, font, "W/S veya Ok: sec | Enter: onay | ESC: cik", 80, H-60, (170, 170, 170))
        pygame.display.flip()
        await asyncio.sleep(0)

async def menu_upgrade(screen, font, big, save_data):
    clock = pygame.time.Clock()
    keys = list(UPGRADES.keys())
    selected = 0

    def can_buy(up_key):
        lvl = save_data["upgrades"][up_key]
        up = UPGRADES[up_key]
        if lvl >= up["max_level"]:
            return False, None
        cost = up["costs"][lvl]
        return save_data["meta"] >= cost, cost

    while True:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    save_save(save_data)
                    return
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(keys)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(keys)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    k = keys[selected]
                    ok, cost = can_buy(k)
                    if ok:
                        save_data["meta"] -= cost
                        save_data["upgrades"][k] += 1
                        save_save(save_data)

        screen.fill((15, 15, 19))
        title = big.render("UPGRADE", True, (245, 245, 245))
        screen.blit(title, (W//2 - title.get_width()//2, 60))
        draw_text(screen, font, f"META: {save_data['meta']}", 80, 130, (220, 220, 220))

        y = 190
        for i, k in enumerate(keys):
            up = UPGRADES[k]
            lvl = save_data["upgrades"][k]
            col = (255, 235, 180) if i == selected else (220, 220, 220)
            line = f"{up['name']}  | Seviye: {lvl}/{up['max_level']}"
            draw_text(screen, font, line, 90, y, col)

            ok, cost = can_buy(k)
            if lvl >= up["max_level"]:
                cost_txt = "MAX"
            else:
                cost_txt = f"Sonraki: {cost} META"
            draw_text(screen, font, cost_txt, 90, y+22, (170, 170, 170))
            y += 58

        draw_text(screen, font, "Enter: satin al | ESC: geri", 80, H-60, (170, 170, 170))
        pygame.display.flip()
        await asyncio.sleep(0)

# ============================================================
# RUN (ASİL OYUN)
# ============================================================

async def run_game(screen, font, big, save_data):
    clock = pygame.time.Clock()

    # Harita seçimi (maç başlayınca)
    current_map = await choose_map(screen, font, big)
    if current_map is None:
        return "menu", 0
    obstacles = current_map["obstacles"]

    player = Player(save_data)
    bullets = []
    enemies = []
    pickups = []
    effects = []  # (type, x, y, a, ttl)
    hazards = []  # boss parçaları ve lazerden gelen hasar kaynakları

    wave = 0
    spawn_timer = 0.0
    spawn_every = ENEMY_SPAWN_EVERY_BASE

    boss_active = False
    boss = None
    boss_warn = 0.0
    last_boss_wave = -1  # aynı dalgada bossun tekrar tekrar spawn olmasını engeller

    def start_boss_phase():
        nonlocal boss_active, boss, boss_warn, last_boss_wave
        boss_active = True
        last_boss_wave = wave
        # Boss gelince mevcut dusmanlar ve boss kaynakli hazardlar temizlensin
        enemies.clear()
        hazards.clear()
        boss = spawn_boss(wave)
        boss_warn = BOSS_ANNOUNCE_TIME

    while True:
        dt = clock.tick(FPS) / 1000.0
        player.hurt_cd = max(0.0, player.hurt_cd - dt)
        player.shield_time = max(0.0, player.shield_time - dt)
        mx, my = pygame.mouse.get_pos()

        shoot_pressed = False
        ability_pressed = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", 0
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "menu", 0
                if player.dead and event.key == pygame.K_r:
                    # ölünce çıkış → meta dönüşümü run sonunda yapılacak
                    return "dead", player.score

                # yetenek tuşları
                for name, a in ABILITIES.items():
                    if event.key == a["key"]:
                        ability_pressed = name

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                shoot_pressed = True

        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            shoot_pressed = True

        # --- Update ---
        if not player.dead:
            # Cooldownları düşür
            for n in player.ability_cd:
                player.ability_cd[n] = max(0.0, player.ability_cd[n] - dt)

            # Yetenek kullan
            if ability_pressed:
                enemies, effects = ability_try_use(player, ability_pressed, enemies, effects)

            # Dash / Slow süreleri
            player.dash_timer = max(0.0, player.dash_timer - dt)
            player.slow_timer = max(0.0, player.slow_timer - dt)

            # Hareket
            ix = (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0)
            iy = (1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0) - (1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0)
            nx, ny = norm(ix, iy)

            speed = player.speed_base
            if player.dash_timer > 0 and player.unlocked("DASH"):
                speed *= ABILITIES["DASH"]["speed_mult"]

            player.x = clamp(player.x + nx * speed * dt, PLAYER_RADIUS, W - PLAYER_RADIUS)
            player.y = clamp(player.y + ny * speed * dt, PLAYER_RADIUS, H - PLAYER_RADIUS)
            # Harita engelleri
            player.x, player.y, _ = apply_obstacle_collisions(player.x, player.y, PLAYER_RADIUS, obstacles)
            player.x = clamp(player.x, PLAYER_RADIUS, W - PLAYER_RADIUS)
            player.y = clamp(player.y, PLAYER_RADIUS, H - PLAYER_RADIUS)

            # Ateş: cooldown + burst
            player.fire_cd_timer = max(0.0, player.fire_cd_timer - dt)
            if shoot_pressed and player.fire_cd_timer <= 0.0 and player.burst_left <= 0:
                player.burst_left = max(1, int(player.burst_count))
                player.burst_timer = 0.0
                player.fire_cd_timer = player.fire_cd

            if player.burst_left > 0:
                player.burst_timer -= dt
                if player.burst_timer <= 0.0:
                    bullets.extend(make_shot_bullets(player, mx, my))
                    player.burst_left -= 1
                    player.burst_timer = player.burst_gap

            # Boss tetikleme: dalga sayısı BOSS_EVERY'e gelince (boss yoksa)
            # Dalga sayımı spawn ile artıyor; boss dalgasında normal spawn durur.
            if (not boss_active) and (wave > 0) and (wave % BOSS_EVERY == 0) and boss is None and (wave != last_boss_wave):
                start_boss_phase()

            # Spawn (boss yokken)
            if not boss_active:
                spawn_timer += dt
                if spawn_timer >= spawn_every:
                    spawn_timer = 0.0
                    wave += 1
                    enemies.append(spawn_enemy(wave))
                    spawn_every = max(ENEMY_SPAWN_MIN, ENEMY_SPAWN_EVERY_BASE - wave * 0.004)
            else:
                # boss uyarı süresi
                if boss_warn > 0:
                    boss_warn = max(0.0, boss_warn - dt)
                else:
                    # boss sahneye girsin ve takip etsin
                    if boss and boss.hp > 0:
                        # boss ekranda yoksa ekle
                        if boss not in enemies:
                            enemies.append(boss)

            # Mermi hareket
            for b in bullets:
                b.x += b.vx * dt
                b.y += b.vy * dt
            bullets = [b for b in bullets if -80 < b.x < W + 80 and -80 < b.y < H + 80]
            # Engellere çarpan mermi silinsin
            bullets = [b for b in bullets if not point_in_obstacles(b.x, b.y, obstacles)]

            # Düşman hareket
            slow_mult = 1.0
            if player.slow_timer > 0 and player.unlocked("SLOW"):
                slow_mult = ABILITIES["SLOW"]["enemy_speed_mult"]

            for e in enemies:
                dx, dy = player.x - e.x, player.y - e.y
                ex, ey = norm(dx, dy)
                e.x += ex * e.speed * slow_mult * dt
                e.y += ey * e.speed * slow_mult * dt
                # Harita engelleri + ekran dışına kaçmayı sınırla
                e.x, e.y, _ = apply_obstacle_collisions(e.x, e.y, e.r, obstacles)
                e.x = clamp(e.x, e.r, W - e.r)
                e.y = clamp(e.y, e.r, H - e.r)

            # Efekt TTL
            new_fx = []
            for fx in effects:
                t = fx[0]
                if t == "bomb":
                    _, x, y, rad, ttl = fx
                    ttl -= dt
                    if ttl > 0:
                        new_fx.append((t, x, y, rad, ttl))
                elif t == "heal":
                    _, x, y, a, ttl = fx
                    ttl -= dt
                    if ttl > 0:
                        new_fx.append((t, x, y, a, ttl))
                elif t == "slow":
                    _, x, y, a, ttl = fx
                    ttl -= dt
                    if ttl > 0:
                        new_fx.append((t, x, y, a, ttl))
            effects = new_fx

            
            # Boss özel saldırıları (parçalar + lazer) ve hazard güncelleme
            for e in enemies:
                if not e.is_boss or e.hp <= 0:
                    continue

                # Tired (yorulma) penceresi: bu sırada boss'a vurulabilir
                if getattr(e, "tired_timer", 0.0) > 0:
                    e.tired_timer = max(0.0, e.tired_timer - dt)

                # Parça orbit + atış
                for p in getattr(e, "parts", []):
                    if p["hp"] <= 0:
                        continue
                    p["angle"] += 1.4 * dt
                    p["shot_cd"] -= dt
                    if p["shot_cd"] <= 0 and getattr(e, "tired_timer", 0.0) <= 0 and e.laser_state != "fire":
                        px = e.x + math.cos(p["angle"]) * p["dist"]
                        py = e.y + math.sin(p["angle"]) * p["dist"]
                        dx, dy = player.x - px, player.y - py
                        vx, vy = norm(dx, dy)
                        speed = 210
                        hazards.append(Hazard(px, py, vx * speed, vy * speed, dmg=20, r=6))
                        p["shot_cd"] = random.uniform(1.25, 1.85)

                # Lazer döngüsü
                e.next_attack_in -= dt
                if e.laser_state == "idle" and e.next_attack_in <= 0 and getattr(e, "tired_timer", 0.0) <= 0:
                    e.laser_state = "charge"
                    e.laser_timer = 1.35
                    dx, dy = player.x - e.x, player.y - e.y
                    lx, ly = norm(dx, dy)
                    e.laser_dir = (lx, ly)
                    e.laser_angle = math.atan2(ly, lx)
                    # dönüş yönünü rastgele seç (daha zor: lazer tarama)
                    e.laser_spin = random.choice([-1, 1]) * 2.8

                if e.laser_state == "charge":
                    e.laser_timer -= dt
                    if e.laser_timer <= 0:
                        e.laser_state = "fire"
                        e.laser_timer = 0.80
                        e.laser_tick = 0.0

                elif e.laser_state == "fire":
                    e.laser_timer -= dt
                    # lazer kendi etrafında döner
                    e.laser_angle += e.laser_spin * dt
                    e.laser_dir = (math.cos(e.laser_angle), math.sin(e.laser_angle))
                    lx, ly = e.laser_dir
                    px, py = player.x - e.x, player.y - e.y
                    proj = px * lx + py * ly
                    if 0 < proj < 640:
                        perp = abs(px * (-ly) + py * lx)
                        if perp < 14:
                            # Laser tick: every 0.1s deal 5 damage
                            e.laser_tick -= dt
                            if e.laser_tick <= 0:
                                player.take_damage(5)
                                e.laser_tick = 0.1
                    if e.laser_timer <= 0:
                        e.laser_state = "idle"
                        # Lazerden sonra yorulur: BU SIRADA boss'a vurulabilir
                        e.tired_timer = 4.6
                        e.next_attack_in = random.uniform(3.3, 4.4)

            # Hazard hareket + engel + ekran temizleme
            for hz in hazards:
                hz.x += hz.vx * dt
                hz.y += hz.vy * dt
            hazards = [hz for hz in hazards if -120 < hz.x < W + 120 and -120 < hz.y < H + 120]
            hazards = [hz for hz in hazards if not point_in_obstacles(hz.x, hz.y, obstacles)]

            # Hazard -> oyuncu çarpışma
            for hz in hazards:
                if circle_hit(hz.x, hz.y, hz.r, player.x, player.y, PLAYER_RADIUS):
                    player.take_damage(hz.dmg)
                    hz.x, hz.y = -9999, -9999
            hazards = [hz for hz in hazards if hz.x > -9000]


            # Boss parçalarına ateş: parçalar her zaman vurulabilir (boss'u zayıflatır)
            for e in enemies:
                if not e.is_boss or e.hp <= 0:
                    continue
                for p in getattr(e, "parts", []):
                    if p["hp"] <= 0:
                        continue
                    px = e.x + math.cos(p["angle"]) * p["dist"]
                    py = e.y + math.sin(p["angle"]) * p["dist"]
                    for b in bullets:
                        if circle_hit(px, py, p["r"], b.x, b.y, b.r):
                            p["hp"] -= b.dmg
                            b.x, b.y = -9999, -9999
                    if p["hp"] <= 0:
                        # parça ölünce boss daha sık yorulsun
                        e.next_attack_in = max(1.6, e.next_attack_in - 0.4)

# Çarpışmalar: mermi -> düşman
            for e in enemies:
                if e.hp <= 0:
                    continue
                for b in bullets:
                    if circle_hit(e.x, e.y, e.r, b.x, b.y, b.r):
                        # Boss sadece 'yorulduğunda' hasar alır
                        if e.is_boss and getattr(e, 'tired_timer', 0.0) <= 0:
                            b.x, b.y = -9999, -9999
                            continue
                        e.hp -= b.dmg
                        b.x, b.y = -9999, -9999
                        if e.hp <= 0:
                            # skor
                            if e.is_boss:
                                player.score += BOSS_CLEAR_REWARD_SCORE
                            else:
                                player.score += 10

                            # pickup (boss'ta daha cömert)
                            if (not e.is_boss and random.random() < PICKUP_SPAWN_CHANCE) or (e.is_boss and random.random() < 0.85):
                                kind = random.choice(["heal", "power", "spd"])
                                pickups.append(Pickup(e.x, e.y, kind))
                        break

            bullets = [b for b in bullets if b.x != -9999]
            enemies = [e for e in enemies if e.hp > 0]

            # Boss öldüyse boss fazını bitir
            if boss_active and boss and boss.hp <= 0:
                boss_active = False
                boss = None
                # meta ödül ver
                save_data["meta"] += BOSS_CLEAR_REWARD_META
                save_save(save_data)
                # ufak nefes alma: spawn aralığını geçici yükselt
                spawn_timer = 0.0
                spawn_every = max(spawn_every, 0.55)

            # Düşman -> oyuncu çarpışma
            for e in enemies:
                if player.hurt_cd <= 0.0 and circle_hit(e.x, e.y, e.r, player.x, player.y, PLAYER_RADIUS):
                    base = 22 + wave * 0.15
                    if e.is_boss:
                        base *= 2.2
                    dmg = int(base)
                    player.take_damage(dmg)

                    # Hit cooldown (golem/boss gibi yakın temas ölümcüllüğünü düşürür)
                    player.hurt_cd = 1.05 if e.is_boss else 0.75

                    # knockback
                    dx, dy = e.x - player.x, e.y - player.y
                    kx, ky = norm(dx, dy)
                    e.x += kx * (26 if e.is_boss else 18)
                    e.y += ky * (26 if e.is_boss else 18)

                    if player.hp <= 0:
                        player.dead = True
                        break

            # Pickup -> oyuncu
            remain = []
            for pu in pickups:
                # Miknatis: pickup'lari cek
                if getattr(player, "magnet_radius", 0) > 0:
                    dx = player.x - pu.x
                    dy = player.y - pu.y
                    d2 = dx*dx + dy*dy
                    if d2 < player.magnet_radius * player.magnet_radius and d2 > 1.0:
                        d = math.sqrt(d2)
                        pull = 260.0  # px/s
                        pu.x += (dx / d) * pull * dt
                        pu.y += (dy / d) * pull * dt

                if circle_hit(pu.x, pu.y, pu.r, player.x, player.y, PLAYER_RADIUS):
                    if pu.kind == "heal":
                        player.hp = min(player.hp_max, player.hp + 35)
                    elif pu.kind == "spd":
                        player.speed_base += 10
                    else:
                        # power: vuruş hissi
                        if player.multi < 6:
                            player.multi += 1
                            player.spread_deg = min(28, player.spread_deg + 2)
                        elif player.burst_count < 6:
                            player.burst_count += 1
                        else:
                            player.damage += 2
                else:
                    remain.append(pu)
            pickups = remain

        # --- Draw ---
        draw_map_background(screen, current_map)

        # Obstacles
        draw_map_obstacles(screen, current_map)

        # Aim line
        pygame.draw.line(screen, (180, 180, 180), (int(player.x), int(player.y)), (mx, my), 1)

        # Player
        pygame.draw.circle(screen, (90, 200, 130), (int(player.x), int(player.y)), PLAYER_RADIUS)

        # Bullets
        for b in bullets:
            pygame.draw.circle(screen, (235, 235, 235), (int(b.x), int(b.y)), b.r)

        # Boss parçaları + lazer göstergesi + hazardlar
        for e in enemies:
            if not getattr(e, "is_boss", False) or e.hp <= 0:
                continue

            # Parçalar
            for p in getattr(e, "parts", []):
                if p["hp"] <= 0:
                    continue
                px = e.x + math.cos(p["angle"]) * p["dist"]
                py = e.y + math.sin(p["angle"]) * p["dist"]
                pygame.draw.circle(screen, (120, 200, 255), (int(px), int(py)), p["r"])
                # küçük can barı
                fracp = p["hp"] / 90
                wbarp = 24
                hpwp = int(wbarp * max(0.0, min(1.0, fracp)))
                pygame.draw.rect(screen, (35, 35, 40), (int(px - wbarp/2), int(py - p["r"] - 10), wbarp, 4))
                pygame.draw.rect(screen, (120, 200, 255), (int(px - wbarp/2), int(py - p["r"] - 10), hpwp, 4))

            # Lazer telegraph / beam
            if getattr(e, "laser_state", "idle") in ("charge", "fire"):
                lx, ly = getattr(e, "laser_dir", (0.0, 1.0))
                x2 = e.x + lx * 760
                y2 = e.y + ly * 760
                col = (255, 220, 120) if e.laser_state == "charge" else (255, 80, 80)
                pygame.draw.line(screen, col, (int(e.x), int(e.y)), (int(x2), int(y2)), 4 if e.laser_state == "charge" else 10)

        # Hazardlar (boss parçalarının mermileri)
        for hz in hazards:
            pygame.draw.circle(screen, (160, 220, 255), (int(hz.x), int(hz.y)), hz.r)

        # Enemies + hp bar
        for e in enemies:
            col = (240, 140, 70) if e.is_boss else (220, 80, 90)
            pygame.draw.circle(screen, col, (int(e.x), int(e.y)), e.r)

            wbar = 36 if e.is_boss else 28
            frac = e.hp / max(1, e.hp_max)
            hpw = int(wbar * frac)
            pygame.draw.rect(screen, (35, 35, 40), (int(e.x - wbar/2), int(e.y - e.r - 12), wbar, 5))
            pygame.draw.rect(screen, col, (int(e.x - wbar/2), int(e.y - e.r - 12), hpw, 5))

        # Pickups
        for pu in pickups:
            if pu.kind == "heal":
                col = (80, 170, 240)
            elif pu.kind == "power":
                col = (240, 200, 80)
            else:
                col = (170, 110, 240)
            pygame.draw.circle(screen, col, (int(pu.x), int(pu.y)), pu.r)

        # Effects
        for fx in effects:
            if fx[0] == "bomb":
                _, x, y, rad, ttl = fx
                pygame.draw.circle(screen, (230, 230, 255), (int(x), int(y)), int(rad), 2)
            elif fx[0] == "heal":
                _, x, y, a, ttl = fx
                pygame.draw.circle(screen, (80, 170, 240), (int(x), int(y)), 26, 2)
            elif fx[0] == "slow":
                _, x, y, a, ttl = fx
                pygame.draw.circle(screen, (170, 110, 240), (int(player.x), int(player.y)), 34, 2)

        # UI: HP
        pygame.draw.rect(screen, (35, 35, 40), (16, 14, 240, 14))
        hpw = int(240 * (player.hp / max(1, player.hp_max)))
        pygame.draw.rect(screen, (90, 200, 130), (16, 14, hpw, 14))

        draw_text(screen, font, f"HP {player.hp}/{player.hp_max}", 16, 34)
        draw_text(screen, font, f"Skor: {player.score}", 16, 60)
        draw_text(screen, font, f"Dalga: {wave}   Dusman: {len(enemies)}", 16, 86)
        draw_text(screen, font, f"Hasar:{player.damage} Multi:{player.multi} Spread:{player.spread_deg} Burst:{player.burst_count}", 16, 112)
        draw_text(screen, font, "A: Q=BOMB, E=HEAL, F=SLOW, LSHIFT=DASH (skorla acilir)", 16, H - 30, (170, 170, 170))

        # Yetenek UI (kilitli/açık + cd)
        y0 = 140
        for name, a in ABILITIES.items():
            unlocked = player.unlocked(name)
            cd = player.ability_cd[name]
            tag = "ACIK" if unlocked else f"KILIT ({a['unlock_score']})"
            cd_txt = f"CD:{cd:.1f}s" if unlocked else ""
            col = (255, 235, 180) if unlocked else (140, 140, 140)
            draw_text(screen, font, f"{name}: {tag} {cd_txt}", 16, y0, col)
            y0 += 22

        # Boss UI
        if boss_active:
            if boss_warn > 0:
                msg = big.render("BOSS GELIYOR!", True, (255, 235, 180))
                screen.blit(msg, (W//2 - msg.get_width()//2, 40))
            elif boss:
                # boss hp bar üstte
                pygame.draw.rect(screen, (35, 35, 40), (W//2 - 260, 14, 520, 14))
                bw = int(520 * (boss.hp / max(1, boss.hp_max)))
                pygame.draw.rect(screen, (240, 140, 70), (W//2 - 260, 14, bw, 14))
                draw_text(screen, font, f"BOSS HP {boss.hp}/{boss.hp_max}", W//2 - 70, 34, (240, 140, 70))

        # Dead overlay
        if player.dead:
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            screen.blit(overlay, (0, 0))
            msg = big.render("OLDUN", True, (255, 255, 255))
            screen.blit(msg, (W//2 - msg.get_width()//2, H//2 - 90))

            meta_gain = convert_score_to_meta(player.score)
            msg2 = font.render(f"Skor: {player.score}  ->  META +{meta_gain}", True, (230, 230, 230))
            screen.blit(msg2, (W//2 - msg2.get_width()//2, H//2 - 25))

            msg3 = font.render("R: menuye don (meta eklenir) | ESC: menu", True, (200, 200, 200))
            screen.blit(msg3, (W//2 - msg3.get_width()//2, H//2 + 20))

        pygame.display.flip()

        await asyncio.sleep(0)

# ============================================================
# UYGULAMA AKIŞI
# ============================================================

async def main():
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.SCALED)
    global W, H
    W, H = screen.get_size()
    pygame.display.set_caption("Arena - Boss(100) + Meta + Yetenek Kilidi")
    font = pygame.font.SysFont(None, 28)
    big = pygame.font.SysFont(None, 56)

    save_data = load_save()

    while True:
        action = await menu_main(screen, font, big, save_data)
        if action == "quit":
            if not IS_WEB:
                pygame.quit()
            return
        if action == "upgrade":
            await menu_upgrade(screen, font, big, save_data)
            save_data = load_save()
            continue
        if action == "market":
            await menu_market(screen, font, big, save_data)
            save_data = load_save()
            continue
        if action == "start":
            result, run_score = await run_game(screen, font, big, save_data)

            # Run bitti/öldü → meta ekle
            if run_score > 0:
                update_top_scores(save_data, run_score)
                gain = convert_score_to_meta(run_score)
                save_data["meta"] += gain
                save_save(save_data)
                save_data = load_save()

            if result == "quit":
                if not IS_WEB:
                    pygame.quit()
                return
            # menuye dön
            continue


if __name__ == "__main__":
    asyncio.run(main())
