import streamlit as st
import numpy as np
import random
from PIL import Image, ImageDraw
import time
import warnings

warnings.filterwarnings("ignore")

# ---------------------- 1. 全局配置（移除轨迹+强化逻辑） ----------------------
st.set_page_config(
    page_title="西南大学图书馆逻辑化动线模拟",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""
<style>
    .stMetric {padding: 8px; border-radius: 4px;}
    .sidebar .sidebar-content {padding: 15px;}
</style>
""", unsafe_allow_html=True)

st.title("西南大学中心图书馆空间动线模拟（15秒）")
st.markdown("### 逻辑化动线 | 纯圆点移动 | 无拖尾轨迹")

# 保留地图核心尺寸
MAP_WIDTH = 800
MAP_HEIGHT = 800
# 简化规则：仅保留颜色、目标和速度，移除轨迹相关配置
RULE_MAP = {
    "undergrad": {"target": "study", "color": (0, 0, 255), "speed": 1.0},
    "graduate": {"target": "study", "color": (255, 0, 0), "speed": 1.1},
    "staff": {"target": "library", "color": (0, 255, 0), "speed": 0.9},
    "visitor": {"target": "visitor", "color": (255, 255, 0), "speed": 1.2}
}

# ---------------------- 2. 侧边栏配置（简化界面） ----------------------
with st.sidebar:
    st.header("📌 模拟配置")
    scene = st.selectbox(
        "模拟情景（动线规则）",
        ["日常模式", "考试周（自习区聚集）", "闭馆（出口疏散）"],
        index=0
    )

    # 优化移动参数（保证流畅+逻辑）
    scene_params = {
        "日常模式": {"agents": 25, "base_speed": 6.0, "stay": 1, "fps": 12},
        "考试周（自习区聚集）": {"agents": 35, "base_speed": 5.5, "stay": 3, "fps": 12},
        "闭馆（出口疏散）": {"agents": 20, "base_speed": 7.5, "stay": 1, "fps": 12}
    }
    params = scene_params[scene]
    total_agents = params["agents"]
    base_speed = params["base_speed"]
    stay_time = params["stay"]
    fps = params["fps"]
    TOTAL_TIME = 15
    TOTAL_FRAMES = TOTAL_TIME * fps

    agent_size = st.slider("圆点尺寸", 6, 10, 8, 1, help="建议8，清晰可见")
    
    st.divider()
    st.header("📖 核心规则")
    st.write("🔵 本科生 → 自习区 | 🟥 研究生 → 自习区")
    st.write("🟩 工作人员 → 图书馆 | 🟨 访客 → 访客区")
    st.write("🚪 闭馆 → 所有人直奔主出口")
    st.write("🛣️ 道路：白色边框内为可通行区")

    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button("▶️ 开始模拟", type="primary", use_container_width=True)
    with col2:
        reset_btn = st.button("🔄 重置模拟", use_container_width=True)

# ---------------------- 3. 保留高还原地图（完全不变） ----------------------
CORE_ZONES = {
    "library": {"pos": (80, 40, 120, 90), "name": "中心图书馆（办公）", "color": (190, 190, 190), "text_bg": (255,255,255)},
    "study": {"pos": (220, 40, 80, 90), "name": "自习区（核心）", "color": (170, 170, 170), "text_bg": (255,255,255)},
    "visitor": {"pos": (0, 0, MAP_WIDTH, 60), "name": "访客通行区", "color": (240, 240, 200), "text_bg": (0,0,0)},
    "exit": {"pos": (680, 680, 80, 80), "name": "主出口", "color": (140, 255, 140), "text_bg": (0,0,0)},
    "bayi": {"pos": (320, 40, 120, 90), "name": "八一礼赞（景观）", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "liyuan5": {"pos": (460, 40, 120, 90), "name": "梨园五舍（宿舍）", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "tongjiegou": {"pos": (600, 40, 120, 90), "name": "砼结构楼（教辅）", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "liyuan_side": {"pos": (20, 160, 120, 90), "name": "梨园五舍侧楼", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "qikan": {"pos": (40, 280, 120, 90), "name": "期刊社下层", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "water": {"pos": (280, 280, 320, 180), "name": "人工湖（不可通行）", "color": (100, 180, 220), "text_bg": (255,255,255)},
    "badminton": {"pos": (80, 600, 220, 90), "name": "羽毛球场", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "park1": {"pos": (700, 620, 60, 120), "name": "停车位1", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "park2": {"pos": (300, 720, 180, 40), "name": "停车位2", "color": (100, 100, 100), "text_bg": (255,255,255)},
    "park3": {"pos": (580, 720, 180, 40), "name": "停车位3", "color": (100, 100, 100), "text_bg": (255,255,255)}
}

ROAD_SYSTEM = [
    {"pos": (MAP_WIDTH//2, 80), "dir": "h", "text": "主干道（东西向）", "width": 50},
    {"pos": (80, MAP_HEIGHT//2), "dir": "v", "text": "主干道（南北向）", "width": 50},
    {"pos": (MAP_WIDTH//2, 650), "dir": "h", "text": "次干道（东西向）", "width": 30},
    {"pos": (700, MAP_HEIGHT//2), "dir": "v", "text": "次干道（南北向）", "width": 30}
]
ROAD_BORDER_WIDTH = 5

@st.cache_data(persist=True)
def create_passable_mask(w, h):
    mask = np.ones((h, w), dtype=bool)
    for zone in CORE_ZONES.values():
        x, y, zw, zh = zone["pos"]
        mask[y:y+zh, x:x+zw] = False
    return mask

passable_mask = create_passable_mask(MAP_WIDTH, MAP_HEIGHT)

@st.cache_data(persist=True)
def draw_real_map(w, h):
    img = Image.new("RGB", (w, h), (245, 245, 245))
    draw = ImageDraw.Draw(img)

    for zone_name, zone in CORE_ZONES.items():
        x, y, zw, zh = zone["pos"]
        draw.rectangle([x, y, x+zw, y+zh], fill=zone["color"])
        text = zone["name"]
        text_w = len(text) * 10
        text_h = 20
        text_x = x + 10 if x + text_w < x+zw else x + zw - text_w - 10
        text_y = y + 10 if y + text_h < y+zh else y + zh - text_h - 10
        draw.rectangle([text_x-2, text_y-2, text_x+text_w+2, text_y+text_h+2], fill=zone["text_bg"])
        text_color = (0,0,0) if zone["text_bg"] == (255,255,255) else (255,255,255)
        draw.text((text_x, text_y), text, fill=text_color, font_size=12, stroke_width=1)

    for road in ROAD_SYSTEM:
        x, y = road["pos"]
        r_width = road["width"]
        if road["dir"] == "h":
            draw.rectangle([0, y-r_width//2, w, y+r_width//2], outline="white", width=ROAD_BORDER_WIDTH)
            arrow_size = 8
            draw.polygon([(x+30, y), (x+20, y-arrow_size), (x+20, y+arrow_size)], fill="black")
            draw.polygon([(x-30, y), (x-20, y-arrow_size), (x-20, y+arrow_size)], fill="black")
        else:
            draw.rectangle([x-r_width//2, 0, x+r_width//2, h], outline="white", width=ROAD_BORDER_WIDTH)
            draw.polygon([(x, y+30), (x-arrow_size, y+20), (x+arrow_size, y+20)], fill="black")
            draw.polygon([(x, y-30), (x-arrow_size, y-20), (x+arrow_size, y-20)], fill="black")
        text_x = x - 60 if road["dir"] == "h" else x - 60
        text_y = y - 30 if road["dir"] == "h" else y - 15
        draw.text((text_x, text_y), road["text"], fill="black", font_size=11, stroke_width=1)

    return img

if "real_base_map" not in st.session_state:
    st.session_state["real_base_map"] = draw_real_map(MAP_WIDTH, MAP_HEIGHT)

# ---------------------- 4. 人群类（核心：逻辑化动线+纯圆点移动+修复NameError） ----------------------
class LogicalRulePerson:
    def __init__(self, ptype):
        self.type = ptype
        self.cfg = RULE_MAP[ptype]
        self.color = self.cfg["color"]
        self.speed = base_speed * self.cfg["speed"]
        self.stay_time = stay_time
        self.stay_counter = 0

        # 初始位置：主干道中心+远离目标区（保证移动逻辑）
        self.pos = self._init_on_main_road()
        # 目标点：规则区域入口（更符合真实动线）
        self.target = self._get_logical_target()

    def _init_on_main_road(self):
        """初始位置：优先在主干道中心生成，保证移动路径沿道路"""
        target_zone = self.cfg["target"] if scene != "闭馆（出口疏散）" else "exit"
        tx, ty, tw, th = CORE_ZONES[target_zone]["pos"]
        target_center = np.array([tx + tw//2, ty + th//2])

        while True:
            # 优先在主干道中心生成初始位置
            x = random.choice([MAP_WIDTH//2, 80, 700]) + random.randint(-30, 30)
            y = random.choice([MAP_HEIGHT//2, 80, 650]) + random.randint(-30, 30)
            x = np.clip(x, ROAD_BORDER_WIDTH, MAP_WIDTH-ROAD_BORDER_WIDTH)
            y = np.clip(y, ROAD_BORDER_WIDTH, MAP_HEIGHT-ROAD_BORDER_WIDTH)
            
            if passable_mask[int(y), int(x)]:
                pos = np.array([x, y])
                if np.linalg.norm(pos - target_center) >= 120:
                    return pos
        return np.array([MAP_WIDTH//2, MAP_HEIGHT//2])

    def _get_logical_target(self):
        """目标点：规则区域的入口位置，而非中心（修复NameError：zw→tw）"""
        if scene == "闭馆（出口疏散）":
            target_zone = "exit"
        else:
            target_zone = self.cfg["target"]
        
        tx, ty, tw, th = CORE_ZONES[target_zone]["pos"]
        # 目标点选在区域入口（靠近主干道的一侧）
        if target_zone == "study":
            # 自习区入口在西侧（靠近主干道）
            target_pos = np.array([tx + 10, ty + th//2])
        elif target_zone == "library":
            # 图书馆入口在东侧（靠近主干道）【修复：zw→tw】
            target_pos = np.array([tx + tw - 10, ty + th//2])
        elif target_zone == "visitor":
            # 访客区入口在南侧（靠近主干道）
            target_pos = np.array([MAP_WIDTH//2, ty + th - 10])
        else:  # exit
            # 出口入口在北侧（靠近次干道）
            target_pos = np.array([tx + tw//2, ty + 10])
        
        # 小幅随机偏移，避免扎堆
        target_pos += np.random.randint(-10, 10, 2)
        target_pos = np.clip(target_pos, tx+5, tx+tw-5)
        target_pos[1] = np.clip(target_pos[1], ty+5, ty+th-5)
        
        if passable_mask[int(target_pos[1]), int(target_pos[0])]:
            return target_pos
        return np.array([tx + tw//2, ty + th//2])

    def move(self):
        """逻辑化移动：沿道路方向+避障+目标明确"""
        # 到达目标后，在规则区域内微调（避免静止）
        if np.linalg.norm(self.pos - self.target) < 8:
            self.stay_counter += 1
            if self.stay_counter >= self.stay_time:
                self.target = self._get_logical_target()
                self.stay_counter = 0
            else:
                # 微幅随机移动（模拟真实徘徊）
                self.pos += (np.random.rand(2) - 0.5) * 3
                self.pos = np.clip(self.pos, ROAD_BORDER_WIDTH, MAP_WIDTH-ROAD_BORDER_WIDTH)
        else:
            # 沿道路方向移动：优先沿主干道方向
            direction = self.target - self.pos
            norm = np.linalg.norm(direction)
            if norm > 0:
                direction = direction / norm
                # 道路约束：如果移动方向偏离主干道，平滑修正
                main_roads_x = [MAP_WIDTH//2, 80, 700]
                closest_road_x = min(main_roads_x, key=lambda x: abs(x - self.pos[0]))
                if abs(self.pos[0] - closest_road_x) > 20:
                    # 向主干道平滑偏移
                    direction[0] += (closest_road_x - self.pos[0]) * 0.02
                    direction = direction / np.linalg.norm(direction)
                new_pos = self.pos + direction * self.speed
                self.pos = new_pos

        # 边界+避障（严格沿道路）
        self.pos = np.clip(self.pos, ROAD_BORDER_WIDTH, MAP_WIDTH-ROAD_BORDER_WIDTH)
        if not passable_mask[int(self.pos[1]), int(self.pos[0])]:
            # 向最近主干道强制偏移
            main_roads_x = [MAP_WIDTH//2, 80, 700]
            closest_road_x = min(main_roads_x, key=lambda x: abs(x - self.pos[0]))
            self.pos[0] = np.clip(self.pos[0] + (closest_road_x - self.pos[0])*0.15, ROAD_BORDER_WIDTH, MAP_WIDTH-ROAD_BORDER_WIDTH)

        return self.pos

# ---------------------- 5. 会话状态（简化） ----------------------
if "sim_running" not in st.session_state:
    st.session_state.update({
        "sim_running": False,
        "people": [],
        "frame_idx": 0,
        "start_time": 0,
        "load_state": "idle"
    })

if reset_btn:
    st.session_state.update({
        "sim_running": False,
        "people": [],
        "frame_idx": 0,
        "start_time": 0,
        "load_state": "idle"
    })
    st.rerun()

# ---------------------- 6. 模拟主逻辑（纯圆点移动+无拖尾） ----------------------
map_placeholder = st.empty()
map_placeholder.image(
    st.session_state["real_base_map"],
    width=MAP_WIDTH,
    use_container_width=False
)
status_placeholder = st.empty()
time_placeholder = st.sidebar.empty()

# 启动模拟
if start_btn and not st.session_state["sim_running"]:
    st.session_state["load_state"] = "loading"
    status_placeholder.info("🔄 初始化逻辑化动线场景...")
    
    # 按比例生成人群
    person_types = ["undergrad"]*10 + ["graduate"]*8 + ["staff"]*4 + ["visitor"]*3
    random.shuffle(person_types)
    st.session_state["people"] = [LogicalRulePerson(t) for t in person_types[:total_agents]]
    
    st.session_state["sim_running"] = True
    st.session_state["start_time"] = time.time()
    st.session_state["frame_idx"] = 0
    st.session_state["load_state"] = "running"
    status_placeholder.empty()

# 运行模拟（纯圆点移动）
if st.session_state["sim_running"]:
    people = st.session_state["people"]
    frame_idx = st.session_state["frame_idx"]
    start_time = st.session_state["start_time"]

    if frame_idx < TOTAL_FRAMES:
        elapsed = time.time() - start_time
        remaining = max(0, TOTAL_TIME - elapsed)
        time_placeholder.metric("⏱️ 剩余时间", f"{remaining:.1f}秒")

        # 基于高还原底图合成帧（仅绘制圆点）
        current_img = st.session_state["real_base_map"].copy()
        draw = ImageDraw.Draw(current_img)

        # 仅绘制移动的圆点（无轨迹）
        for p in people:
            pos = p.move()
            x, y = int(pos[0]), int(pos[1])
            draw.ellipse(
                [x-agent_size, y-agent_size, x+agent_size, y+agent_size],
                fill=p.color,
                outline="black",
                width=2
            )

        # 刷新图像（固定尺寸，无抖动）
        map_placeholder.image(current_img, width=MAP_WIDTH, use_container_width=False)

        # 控制帧率（流畅移动）
        st.session_state["frame_idx"] += 1
        time.sleep(1/fps - 0.005)
        st.rerun()
    else:
        # 模拟结束
        st.session_state["sim_running"] = False
        time_placeholder.empty()
        status_placeholder.success("✅ 逻辑化动线模拟完成！核心结论如下：")
        
        # 统计核心区人数（匹配CORE_ZONES名称）
        zone_count = {"自习区（核心）":0, "中心图书馆（办公）":0, "主出口":0, "访客通行区":0}
        for p in people:
            x, y = p.pos
            for zone_key, zone_info in CORE_ZONES.items():
                zone_name = zone_info["name"]
                if zone_name in zone_count:
                    zx, zy, zw, zh = zone_info["pos"]
                    if zx < x < zx+zw and zy < y < zy+zh:
                        zone_count[zone_name] += 1
                        break

        # 分栏展示统计结果
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("📚 自习区人数", zone_count["自习区（核心）"])
        with col2: st.metric("🏢 图书馆人数", zone_count["中心图书馆（办公）"])
        with col3: st.metric("🚪 主出口人数", zone_count["主出口"])
        with col4: st.metric("👥 访客区人数", zone_count["访客通行区"])

        # 智能优化建议
        if scene == "考试周（自习区聚集）" and zone_count["自习区（核心）"] > 25:
            st.warning("⚠️ 优化建议：自习区入口动线压力大，建议拓宽西侧入口通道")
        elif scene == "闭馆（出口疏散）" and zone_count["主出口"] > 15:
            st.warning("⚠️ 优化建议：主出口北侧入口拥堵，建议新增次干道方向的疏散通道")
        else:
            st.info("✅ 空间规划结论：动线逻辑清晰，沿道路移动顺畅，无明显拥堵点")
        
        st.balloons()