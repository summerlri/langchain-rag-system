"""
Locust 压力测试 — 模拟 100 人同时使用 RAG 系统

运行: locust -f tests/locustfile.py --host=http://localhost:8000
Web 界面: http://localhost:8089

场景:
  A: 纯查询 — 登录 + 浏览知识库 + 查看文档 (30%)
  B: 纯问答 — 登录 + 创建会话 + 发问题 + 收集 SSE 流式回答 (50%)
  C: 混合操作 — 登录 + 查看历史会话 + 导出 (20%)
"""
import time
import json
import random
from locust import HttpUser, task, between, events

# 测试问题池（短问题，减少 token 消耗）
QUESTIONS = [
    "iPhone 15 Pro Max 售价多少？",
    "如何退货？",
    "华为 Mate 60 Pro 有什么功能？",
    "小米 14 Ultra 的配置？",
    "支持哪些支付方式？",
    "你们有哪些手机品牌？",
    "空调有什么推荐？",
    "Nike AJ1 多少钱？",
    "配送需要几天？",
    "有价保服务吗？",
]

# 登录信息
USERNAME = "admin"
PASSWORD = "123456"


class RAGUser(HttpUser):
    """模拟普通用户行为"""
    wait_time = between(1, 3)  # 用户操作间隔 1~3 秒
    token = None
    kb_id = None

    def on_start(self):
        """每个虚拟用户启动时先登录（带重试，避免同时登录挤爆服务器）"""
        # 随机延迟 0~3 秒再登录，分散登录压力
        time.sleep(random.uniform(0, 3))

        for attempt in range(3):
            resp = self.client.post(
                "/api/auth/login",
                json={"username": USERNAME, "password": PASSWORD},
                name="登录",
            )
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                return
            # 重试前等待，指数退避
            time.sleep(1 * (attempt + 1))

        # 三次都失败，这个用户后续操作会跳过
        self.token = None

    # ==================== 场景 A: 纯查询 (30%) ====================

    @task(3)
    def browse_knowledge_bases(self):
        """浏览知识库列表"""
        if not self.token:
            return
        with self.client.get(
            "/api/knowledge-bases",
            headers=self.headers,
            name="浏览知识库列表",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    self.kb_id = data[0].get("id")
            else:
                resp.failure(f"状态码: {resp.status_code}")

    @task(3)
    def view_documents(self):
        """查看知识库文档"""
        if not self.token or not self.kb_id:
            return
        with self.client.get(
            f"/api/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers,
            name="查看文档列表",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"状态码: {resp.status_code}")

    # ==================== 场景 B: 纯问答 (50%) ====================

    @task(5)
    def ask_question(self):
        """发起一次 RAG 问答（用 SSE 流式接收）"""
        if not self.token or not self.kb_id:
            return

        # 1. 创建会话
        resp = self.client.post(
            "/api/conversations",
            json={"title": "压测会话", "kb_id": self.kb_id},
            headers=self.headers,
            name="创建会话",
        )
        if resp.status_code != 200:
            return
        conv_id = resp.json().get("id")

        # 2. 发送问题（SSE 流式）
        question = random.choice(QUESTIONS)
        start = time.time()

        with self.client.post(
            f"/api/chat/{conv_id}",
            json={"message": question, "kb_id": self.kb_id},
            headers={
                **self.headers,
                "Content-Type": "application/json",
            },
            name="AI问答(SSE)",
            catch_response=True,
            stream=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"聊天失败: {resp.status_code}")
                return

            # 逐行读取 SSE 事件
            tokens = 0
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if event.get("type") == "done":
                            break
                        elif event.get("type") == "token":
                            tokens += 1
                        elif event.get("type") == "error":
                            resp.failure(f"LLM 错误: {event.get('content')}")
                            break
                    except json.JSONDecodeError:
                        pass

            elapsed = time.time() - start
            resp.success()
            # 上报自定义指标
            events.request.fire(
                request_type="SSE",
                name="流式回答耗时",
                response_time=int(elapsed * 1000),
                response_length=tokens,
            )

    # ==================== 场景 C: 混合操作 (20%) ====================

    @task(2)
    def view_history(self):
        """查看历史会话"""
        if not self.token:
            return
        with self.client.get(
            "/api/conversations",
            headers=self.headers,
            name="查看会话列表",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"状态码: {resp.status_code}")

    @task(2)
    def export_conversation(self):
        """导出对话"""
        if not self.token:
            return
        # 先拿一个会话 ID
        resp = self.client.get(
            "/api/conversations",
            headers=self.headers,
            name="导出-获取会话",
        )
        if resp.status_code == 200:
            convs = resp.json()
            if convs:
                conv_id = convs[0]["id"]
                with self.client.get(
                    f"/api/conversations/{conv_id}/export",
                    headers=self.headers,
                    name="导出对话",
                    catch_response=True,
                ) as exp_resp:
                    if exp_resp.status_code != 200:
                        exp_resp.failure(f"导出失败: {exp_resp.status_code}")

    @task(1)
    def health_check(self):
        """健康检查（轻量请求，观察基线延迟）"""
        self.client.get("/api/health", name="健康检查")


# ==================== 压测完成回调 ====================

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """压测结束后打印汇总"""
    stats = environment.stats
    print("\n" + "=" * 60)
    print("  压力测试完成")
    print("=" * 60)
    print(f"  总请求数: {stats.total.num_requests}")
    print(f"  失败数: {stats.total.num_failures}")
    print(f"  失败率: {stats.total.fail_ratio * 100:.2f}%")
    print(f"  平均响应: {stats.total.avg_response_time:.0f}ms")
    print(f"  P50: {stats.total.get_response_time_percentile(0.5):.0f}ms")
    print(f"  P95: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  P99: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"  RPS: {stats.total.total_rps:.1f}")
    print("=" * 60)
