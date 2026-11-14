# ofm-detel — 关掉 dsh-our-free-model 的五条后台外联通道

给 `dsh-our-free-model` 打一个**只做减法**的本地补丁：让它的插件自己不再往外打电话。

不碰模型车道，不碰 EAC 服务端闸门，不加任何功能。补丁源码开放，你可以逐行读完再决定用不用。

适用版本 **2.8.3**（版本不符会当场报错退出，不会产出一个半残的包）。

---

## 一、先看它到底往外打了什么

这是原始 2.8.3 装上后，**你什么都不点**，它自己会发起的请求：

```
raw.githubusercontent.com/Ebony-Vinyl/dsh-our-free-model/main/feed/announcements.json
cdn.jsdelivr.net/gh/Ebony-Vinyl/dsh-our-free-model@main/feed/announcements.json
gh-proxy.com/https://raw.githubusercontent.com/.../feed/announcements.json
api.ipify.org?format=json
ipinfo.io/json
ipapi.co/json/
api.github.com/repos/Ebony-Vinyl/EAC-Desktop
api.github.com/repos/Ebony-Vinyl/EAC-Pack
api.github.com/repos/Ebony-Vinyl/EAC-design-world
github.com/Ebony-Vinyl/dsh-our-free-model/info/refs?service=git-upload-pack
github.com/Ebony-Vinyl/dsh-our-free-model/commits/main.atom
```

（以上为实测记录，见下方「怎么自证」。）

其中四条是后台自动的，不需要你做任何操作：

| 时机 | 通道 | 做什么 |
|---|---|---|
| 开机 12 秒后，之后每 30 分钟 | 公告 feed | 拉作者仓库里的 JSON，新公告会弹系统通知 |
| 开机 40 秒后，之后每 6 小时 | 自更新 | 拉 manifest，有新版就**下载并安装文件**到插件目录 |
| 每 15 分钟 | 出口探测 | 问三个第三方 IP 回显站「我的公网 IP 是多少」 |
| 开机 + 每 6 小时 | 扩展市场 | 拉**另一个仓库**的签名索引，自动更新时安装并执行其中的 JavaScript |

第 4 条值得单独说一句：它在 README「上表即为本插件全部出网目标」里**没有**。

---

## 二、补丁关掉了什么

| # | 通道 | 处理 |
|---|---|---|
| 1 | 公告 feed | 源清空，`fetchFeed` 直接返回空 |
| 2 | 自更新 | manifest 源清空，下载/安装/替换三个原语改成抛错 |
| 3 | 公网 IP 回显 | 三站全部移除，`detectEgress` 返回 `undefined` |
| 4 | 星数读取 | `api.github.com` 置空，`PickStats` 返回空快照 |
| 5 | 扩展市场 | `registrySources()` 返回 `[]`，开机不再拉，6 小时定时器空转 |
| 6 | 首次公告弹窗 | `settings.onboarding` 门槛不再挂载 |
| 7 | 赞助横幅 | 北辰 API 的 `?aff=…` 联盟链接（文案自带「邀请可获百分之十的返现」） |
| 8 | Star 按钮 | 5 处渲染点全部置 `null` |
| 9 | 升级/重载路由 | `POST /update`、`/update/apply`、`/reload` 一律 409 |

**没有关掉**：EAC 协付车道本身、模型推理、网关面板。以及——服务端的 GitHub star 闸门。那道闸门在作者自己的网关上，改本地副本既够不到也绕不过；本补丁只是让你本地不再被反复要 star，**不声称能解锁任何东西**。

---

## 三、怎么用

```bash
# 1. 取一份当前版本的原始包并解开
npm pack @ebony-vinyl/dsh-our-free-model@2.8.3
mkdir ofm && tar xzf ebony-vinyl-dsh-our-free-model-2.8.3.tgz -C ofm

# 2. 只检查，不写任何东西
python3 patch.py --check ofm/package

# 3. 确认无误再应用
python3 patch.py ofm/package

# 4. 自证：应当 8/8 通过、0 次外联
node verify.mjs ofm/package

# 5. 打包装回
cd ofm/package && npm pack
dsh plugin --profile web add ./dsh-our-free-model-2.8.3.tgz
```

`--check` 会逐条核对锚点。版本不对、或者上游改过那几行，它会**在第一个对不上的地方停下并报行号级错误**，不会写出一半的包。

---

## 四、怎么自证（这一段是重点）

截个图说「我没联网」是没有意义的。这里给的是**可复算的判据**：

`verify.mjs` 在模块加载**之前**就接管了 `globalThis.fetch`、`node:http.request/get`、`node:https.request/get`，并给每个模块注入一个会记录并抛错的 `fetchImpl`。然后真的去调那些入口——`fetchFeed()`、`AnnouncementFeed.poll()`、`detectEgress()`、`pickStats.view()`、`updater.check()`、`updater.apply()`、`registrySources()`。

**判定标准是「拨号次数 = 0」，不是「没报错」。**

我做过反向对照，同一个验证器跑在**未打补丁的原始包**上：

```
$ node verify.mjs <原始 2.8.3>
FAIL  feed: DEFAULT_FEED_SOURCES is empty        (sources remain)
FAIL  feed: fetchFeed() dials nothing            (sources is not iterable)
FAIL  feed: AnnouncementFeed.poll() dials nothing  dials=3
FAIL  probe: detectEgress() dials nothing        dials=3
FAIL  picks: createPickStats().view() dials nothing  dials=6
FAIL  updater: check()/apply() dial nothing      dials=3
FAIL  extensions: registrySources() is empty     (registry sources remain)
PASS  updater: manifest primitives refuse        dials=0

1/8 checks passed, 15 network dial(s) total
```

同一个验证器跑在打过补丁的包上：

```
8/8 checks passed, 0 network dial(s) total
```

**一个永远不会红的闸门不是闸门。** 上面那 15 次拨号和 7 个失败，就是这个验证器不会撒谎的证据。

> 一句话说明它证明到哪：它证明**这五条后台通道不再外联**。它不证明模型车道不发请求——那本来就要发，而且发的是你让它发的东西。

---

## 五、打完补丁之后还剩什么（诚实交代）

补丁不是把插件变成「不联网」。它之后**仍然**会发这两类请求，因为它们是你用它的前提：

| 通道 | 目标 | 为什么留着 |
|---|---|---|
| 模型清册刷新（每 15 分钟） | `opencode.ai/inference/v1/models` | 不拉就不知道现在哪些模型可用 |
| 模型推理（你发消息时） | 各车道上游 | 这就是它存在的意义 |
| EAC 车道（仅桌面端，你主动用） | 作者的自建网关 | 那条车道本身就是网关 |

**这两条我一条都没动，也不建议动。** 想连这都不要，唯一诚实的答案是别装这个插件。

删掉的五条，共同特征是：**它们都不是为了让你发出一条消息**。公告、自更新、查我的公网 IP、数别人的 star、拉可执行扩展——全是围绕插件自己转的。

---

## 六、你需要知道的三件事

**① 这不是「安全加固」，是「减少外联」。**

补丁只让插件不打这五个电话。它不审计插件与模型上游之间的流量，也不改变插件收到的任何东西。

**② 关掉自更新意味着从此不会自动升级。**

上游改了协议、加了新模型、修了 bug，你都得自己重来一遍（重新 pack、重新打补丁、重新装）。这是关掉自更新的必然代价，不是我漏做了什么。

**③ 补丁按行匹配锚点，上游一改就失效。**

这是设计选择，不是缺陷。静默地打一半补丁比打不上更危险。版本号不匹配会直接拒绝执行。

---

## 七、另外一份材料

同仓库的 [`audit/`](audit/) 里有一份针对这个项目的**可核验审计**：出网目标与 README 自述的差异、star 数量作为并发配额公式（`Star {stars} × 1.5`）、联盟返佣链接、issue 投诉与其处理方式。

每一条都带源码行号和你自己就能跑出来的复现命令。**只陈述事实，不提供利用方法。**

---

## 八、许可与边界

- 本补丁：MIT。随便用、随便改、随便转。
- 它修改的是 MIT 许可的第三方包，在**你自己的机器上**、为**你自己的使用**而改。
- 它不绕过任何付费或授权，不冒充他人，不攻击服务端。
- 插件本身的许可与版权归原作者 Ebony-Vinyl，见其仓库 LICENSE。

**免责**：这是对第三方代码的本地修改。用之前请自己读 `patch.py`——它只有 300 行，全是字符串替换，没有别的。
