# 公开视觉测试数据集调研

核对时间：2026-10-09。目标是实际视频输入下的动作选择；不能把数据集动作标签直接当作机器人响应标签。

| 数据集 | 适合验证 | 获取与限制 |
|---|---|---|
| [AIR-Act2Act](https://ai4robot.github.io/air-act2act-en/) | 握手请求、击掌请求、站立等待；含互动双方位置附近拍摄的视角，最接近本项目 | 5000 组、3 视角；RGB 约 45.37 GB；[官方仓库](https://github.com/ai4r/AIR-Act2Act)指向 ETRI，需注册会员；具体数据许可需在下载平台核对，未下载 |
| [KTH](https://www.csc.kth.se/cvap/actions/) | 挥手、鼓掌，以及走路等干扰动作 | 官方提供分动作压缩包与单条 AVI；非商业用途，发表需引用；160×120 分辨率，固定相机，不等同于机器人交互邀请 |
| [ShakeFive2](https://www2.projects.science.uu.nl/shakefive/) | 握手、击掌、碰拳等动作识别；第三人称互动可用作机器人不应介入的候选样本 | 153 段 720p 视频，视频包约104.7 MB；仅研究用途，作者要求使用时联系；未联系、未下载 |
| [TV Human Interactions](https://www.robots.ox.ac.uk/~vgg/data/tv_human_interactions/) | 握手、击掌、拥抱及无目标互动类别 | 300 段电视视频；当前官方页面明确已撤下数据下载，不能作为立即可用的数据源 |

## 推荐测试方法

优先从 AIR-Act2Act 取场景 5（握手）、7（击掌）、2（等待），选择从响应者一侧观察发起者的相机视角，逐帧核对相机编号；不能仅凭类名自动确定第一视角。增加 KTH 挥手和走路样本。

每个片段只向模型提供 8 帧图像和统一的互动规则，隐藏文件名、类别和参考答案。先人工看联系图/视频，标注“互动是否朝向镜头”和正确响应，再评测。分别统计动作识别、请求对象判断、工具选择、格式错误和误触发。

观看两个旁人握手/击掌时，不能直接要求机器人调用 handshake/high_five。场景类别说明正在发生什么，不说明机器人该怎么响应。按人物划分训练/验证/测试，避免同人的相邻片段泄漏。

KTH 官方示例来源：
- https://www.csc.kth.se/cvap/actions/person15_handwaving_d1_uncomp.avi
- https://www.csc.kth.se/cvap/actions/person15_walking_d1_uncomp.avi

## 第二轮检索：机器人视角与下载可用性

2026-10-09 重新核对，优先级如下。以下新数据尚未跑模型评测。

1. **NUSFPID** — [作者页面](https://sites.google.com/view/sanath-narayan/Datasets)。8 类互动，包含观察者参与的第一视角和旁观第三视角，适合区分“与我互动”和“别人之间互动”。[作者提供的下载链接](https://drive.google.com/file/d/0BzMfwZtgNoxFaGtEQzQtU3VlUjQ/view?resourcekey=0-OupoIelP9pns6MUv-drXsw&usp=sharing)。Google Drive 显示 NUSFPID.zip 349M；通过公开下载确认流程读取前 1024 字节，验证 ZIP 文件头 PK0304，下载入口实际可用，无需登录。尚未下载完整包，RGB 内容、各类别数量及完整许可需解压核对；不能声称已覆盖击掌。
2. **UTKinect-FirstPerson** — [官方页面](https://cvrc.ece.utexas.edu/KinectDatasets/FirstPerson.html)。相机安装在机器人上，包含 RGB、深度和分段标签。人形机器人部分有 wave、shake hands；非人形部分有 ignore、pass by、stop、wave 等。两个部分分别约 3.42G、3.33G，各有 8 位参与者。页面要求引用论文；本次实际检查两条 Box 静态 ZIP 链接均返回 HTTP 404，所以不是当前可直接下载的数据源。
3. **JPL-Social / JPL First-Person Interaction** — [作者仓库](https://github.com/biantongfei/SocialEgoNet)。新增互动意图、态度、动作标签与人体/手/脸关键点，适合研究“面向我的互动”。作者提供 JPL_Social.zip 的 Drive 入口，但 README 描述的是关键点与标注，未确认该压缩包包含原始 RGB 视频。原始 JPL 网站本次访问超时，不能当作已取得视频。
4. **GRIT / TsironiGR** — [汉堡大学官方目录](https://www.inf.uni-hamburg.de/en/inst/ab/wtm/research/corpora.html)。640×480 RGB、30fps、6 人、543 段；Hello 明确为面向机器人的单手挥手，另有 Stop、Turn Left/Right 等。比 KTH 双臂摆动更接近应用，但获取需要邮件提供姓名、机构和研究简介。未代发邮件。官网注明 CC BY-NC-SA 3.0 DE，同时列出研究用途、引用及不转交要求。
5. **HRI-Gestures** — [作者仓库](https://github.com/FredHaa/HRI-Gestures)。17 人、20 类、4 个 RealSense 视角，RGB/深度均为1280×720；含停止、跟随、招呼/吸引注意以及站立、走近、走远等被动动作。可直接取得的是骨架；RGB 图像须联系作者，限研究用途。不能把骨架下载说成 RGB 可用。
6. **Dynamic Hand Gesture Recognition Systems** — [Zenodo 数据页](https://zenodo.org/records/16040322)。21 人、27 类、1701 段 Full HD 视频，有动作起止帧表；页面列出22.9GB视频包。作为高清视觉动作补充，尚未核对27类具体语义，不能承诺包括握手或击掌；本次未下载大包。

不优先：HaGRIDv2 是静态 RGB 图片集，即使其配套方法能做动态手势识别，也不能当成真实挥手视频集。EgoNRG 为导航手势、头戴四路单色相机，不是本轮优先寻找的彩色正面社交邀请。

当前建议：先获取 NUSFPID 的小规模测试样本；AIR-Act2Act 仍适合补握手/击掌邀请，但需官方平台注册。只评估已核对的动作与视角，保留第三人称互动和无互动反例。
