# dsh-our-free-model 审计：五件可自己复核的事

对象：`@ebony-vinyl/dsh-our-free-model` **2.8.3**
方法：解包读源码 + 离线调用入口。下文每一条都给出**源码行号**和**你机器上能跑出来的命令**。

**这份材料不包含任何绕过、解锁、攻击方法。** 它只记录「这个包实际做了什么」与「它的自述与实际差在哪」。所有结论都标注了证据等级，推测的地方直说是在推测。

---

## 一、README 说「这就是全部出网目标」，实际不是

README 第 734 行原文：

> 没有号池、没有中转、没有二道贩子。**上表即为本插件全部出网目标**

那一页表格列了 6 项：推理、模型清单、公告与升级清单（raw / jsdelivr）、出口地区判定（ipify / ipinfo / ipapi）。

**表格之外，包里还有 3 类出网目标：**

| 缺失项 | 位置 | 何时发生 |
|---|---|---|
| `api.github.com/repos/*` | `src/picks.js:143` | 打开「推荐项目」页，读三个仓库的 star 数 |
| 扩展市场：`raw.githubusercontent.com` / `cdn.jsdelivr.net` / `gcore.jsdelivr.net` / `gh-proxy.com` | `src/extensions.js:116`（仓库）· `:134-148`（四个源） | **开机一次 + 每 6 小时**，拉**另一个仓库**（`Ebony-Vinyl/ofm-extensions`）的签名索引 |
| `beichenapi.com/register?aff=…` | `client.js:32` | 设置页横幅，链接自带 10% 返佣参数 |

第三项严格说是「用户点击才发」，不算后台外联。但前两项是真的后台。

**复核命令：**

```bash
npm pack @ebony-vinyl/dsh-our-free-model@2.8.3
tar xzf ebony-vinyl-dsh-our-free-model-2.8.3.tgz
grep -n "api.github.com\|ofm-extensions\|beichenapi" package/src/*.js package/client.js
```

`grep` 到 `src/extensions.js` 的 `EXTENSIONS_REPO` 与那 4 个 host，就是 README 表格没写的那一条。

**为什么这条重要**：`src/extensions.js` 不只是读——它带安装与运行。`index.js:1532` 的 6 小时定时器里，`autoUpdateExtensions === true` 时会调用 `extensions.autoUpdate()`。也就是说，一条 README 未列出的通道，在特定设置下是**会下载并执行 JavaScript** 的。作者用 Ed25519 签名校验了它（`PINNED_EXTENSIONS_PUBLIC_KEY`），这是真的防护，但签名防的是「传输中被人改」，不防「作者自己发什么」。

> 证据等级：**直接读到源码 + 行号**。我没有实机挂载验证安装执行路径，那一层是读代码得出的。

---

## 二、Star 数是一个配额公式的输入

`client.js:101`：

```js
'pool.formula': 'Star {stars} × 1.5',
```

`client.js:3733` 决定这行何时显示：

```js
if (pool.poolSource === 'formula') return t('pool.formula').replace('{stars}', String(pool.stars ?? '—'))
```

`{stars}` 是**本仓库的 star 数**，由作者的网关 `/pool` 接口下发（`index.js:237`）。这个数字在界面上的标签是 `'pool.capacity': '号池容量'`（`client.js:98`），旁边还有 `'pool.reach': '容量占用'`（`client.js:100`）。

**读法**：并发容量 = 本仓库 star 数 × 1.5。star 涨，你这一侧显示的容量就涨。

**我标出我在推测的部分**：`poolSource` 由网关返回，服务端怎么算我不看得到；这是**界面文案对它的解释**，不是服务端代码。所以「这个公式就是实际限流算法」我不能断言——我能断言的是「插件告诉用户容量是 star×1.5」，以及这个解释在 README 正文里**找不到**。

**复核命令：**

```bash
grep -n "pool.formula\|poolSource\|pool.capacity" package/client.js
grep -n "star" package/README.md | grep -v "star-history"   # 正文不提容量公式
```

---

## 三、EAC 车道是「登录 GitHub 并 star 本仓库」才解锁的，这条 README 写得很清楚

这一条**不是问题**，是作者明确披露过的设计，我列出来是为了把边界划清：

- `client.js:1024`：`'eac.intro': 'EAC turns are checked server-side: sign in with GitHub and star {repo} to unlock them…'`
- `client.js:140`：`'eac.lockedTitle': '需要 GitHub 授权并 star 仓库后使用'`
- `src/eac-login.js:35`：服务端返回 `status === 'unstarred'` 时，本地判定为未授权
- README 第 702 行：整段解释了这个闸门，并说明「网关默认每 12 小时用保存的授权复查一次 star，取消 star 即在复查窗口内吊销令牌」

**我特意写清楚**：闸门在**作者的服务器上**。本仓库的补丁关掉本地 star 按钮，既够不到也绕不过它，不声称能解锁任何东西。

---

## 四、设置页有 5 个 Star 按钮，另有一整页推荐位

`client.js` 中 `h(StarButton, …)` 出现 **5 次**，位置分别是：

| 行号 | 位置 |
|---|---|
| 3898 | EAC 授权区 |
| 4660 | 「推荐项目」页页头 |
| 7509 | 设置页顶部导航栏 |
| 7591 | 免费模型页 · 鱼缸水位旁 |
| 8211 | EAC 模型页 |

另有 `client.js:4553-4555` 的三个推荐仓库，全部指向作者自己的项目（`EAC-Desktop` / `EAC-Pack` / `EAC-design-world`），并在运行时去 `api.github.com` 取它们的 star/fork 数。

**复核命令：**

```bash
grep -c "h(StarButton" package/client.js          # 5
grep -n "EAC-Desktop\|EAC-Pack\|EAC-design-world" package/client.js
```

---

## 五、这个项目里有人说「追着要 star」，而那个 issue 被关掉时没有回应这一点

Issue **#793**（`我不会再使用ofm了`，2026-11-09，作者 `qq9077`）开篇第一句：

> 首先：追着让我给你star实在让我觉得很难受。我知道这个项目都做了些什么。

账号 `zixin947` 在 2026-11-10 将其标记为 **completed** 关闭，**未回复这条抱怨**。该 issue 至今只有 1 条评论，是发起人自己补的「token is cheep」。

> 我能核到的：`closed` 事件的 actor 是 `zixin947`，仓库 owner 是 `Ebony-Vinyl`。`gh api .../collaborators` 需要 push 权限，我拿不到，所以**他是不是维护者我核不了**，正文只写「关闭者」，不写「维护者」。

同类还有两条，处理方式一致：

| Issue | 标题 | 关闭者与时间 | 是否回应了该 issue 的核心投诉 |
|---|---|---|---|
| **#702** | 骗收藏，打广告的，有感觉吗 | `zixin947` 于 2026-10-30 关闭 | 否（issue 内无人回应「骗收藏」；多名成员反驳发起人） |
| **#655** | 骗人的，没有一个免费可用，里面都是打广告中转站的 | `Ebony-Vinyl` 于 2026-10-31 关闭 | 否（理由针对「上游额度」，未提「打广告」） |

**#655 的关闭理由原文**（`Ebony-Vinyl`，2026-10-31）：

> 关闭并标注：上游服务问题，非本插件代码缺陷（本轮核查确认）。上游 2026-10 下旬集中收紧免费额度/风控/下架，插件侧无法用代码修复。

**这一段我要说公道话**：这个理由对「模型用不了」是成立的——免费额度确实是上游关的。我在自己的 issue #831 里独立测到了同样结论。**但它不是对 #655 标题的回应。** 那条标题说的是「里面都是打广告中转站的」，指的是赞助横幅与推荐位，跟上游额度没有关系。

**复核命令：**

```bash
gh issue view 793 --repo Ebony-Vinyl/dsh-our-free-model
gh issue view 702 --repo Ebony-Vinyl/dsh-our-free-model --comments
gh issue view 655 --repo Ebony-Vinyl/dsh-our-free-model --comments
```

---

## 六、补充：这个项目的正确事实

写这份东西不是为了把它说得一无是处。下面几条同样是事实：

1. **它确实真开源**，MIT，源码可读，补丁可打——本文所有结论都建立在这一点上。
2. **它的上游来源披露得比多数同类详细**，有逐条核对过的目标表（尽管不全）。
3. **它做了真实的工程**：Ed25519 签名的更新清单与扩展索引、凭据 AES-256-GCM 密封、按请求解开且不落盘。这些不是装饰。
4. **免费车道的死因确实是上游**。2026-11 起 `opencode.ai` 对非官方客户端的 TLS 指纹做了区分，官方 CLI 自己也拿到 `Free usage limit reached`。这是我在 issue #831 里实测的，与本插件的代码质量无关。

---

## 七、这份材料的立场

- **只陈述与复现，不给方法。** 上文所有行号都能 `grep` 到，所有 issue 都能 `gh issue view`。没有任何一段是「怎么绕过去」。
- **不主张任何人去攻击这个项目或它的作者。**
- **推测与事实分开标注。** 第二节里「服务端算法」那部分我明确写了看不到。
- **时效**：截至 2.8.3（2026-11-14）。上游随时会改，届时行号会漂。

许可：本文档 CC0。随便引用、随便转。
