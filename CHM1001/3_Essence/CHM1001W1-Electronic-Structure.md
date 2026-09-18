---
course: CHM1001
source: CHM1001W1-Electronic Structure.pptx
slides: 45
extracted: 2026-09-14
tags: [course/essence, chemistry, atomic-structure, quantum]
---

# 第 6 章 · Electronic Structure of Atoms（原子电子结构）

> 一句话主旨：从「光的波动性」出发，经量子化与 Bohr 模型，收敛到用量子数描述的轨道模型，最后落到电子排布的三条规则（Pauli / Hund / 构造原理）。

![第 1 张：本章封面——Chapter 6 Electronic Structure of Atoms（授课用 Lecture Presentation）](figures/CHM1001W1-Electronic-Structure/slide-01.png)

## 1. 为什么从「波」讲起（Electronic Structure）

- 本章主题是**电子结构**——电子的排布与能量
- 但要先讲波：**极小的粒子具有只能用波动性解释的性质**

---

## 2. 电磁波基础（Waves / Electromagnetic Radiation）

- **波长（wavelength, λ）**：相邻波上对应点之间的距离
- 理解原子电子结构，必须先理解电磁辐射的本质

![第 3 张：波长的定义（相邻对应点之间的距离）](figures/CHM1001W1-Electronic-Structure/slide-03.png)

- **频率（frequency, ν）**：单位时间内通过某定点的波数
- 波速相同时：**波长越长 → 频率越小**
- 图中若左方两行各占 1 秒，则频率分别为 **2 s⁻¹** 与 **4 s⁻¹**

![第 4 张：波长与频率的反比关系（同为 1 s，上方 2 个波、下方 4 个波）](figures/CHM1001W1-Electronic-Structure/slide-04.png)

- 所有电磁辐射传播速度相同：**光速 $c = 3.00\times10^{8}\ \mathrm{m/s}$**
- 关系式：$c = \lambda\nu$　`[待核实]` 提取文本里该式符号丢失，仅剩 `c =`；由 λ、ν 的定义推得，请对照第 5 张原图确认

![第 5 张：电磁波谱与 c = λν 关系式](figures/CHM1001W1-Electronic-Structure/slide-05.png)

---

## 3. 能量量子化：Planck 与 Einstein

- **波动性解释不了的现象**：物体温度升高后为什么会发光
- Max Planck 的解法：能量以**一份一份**的形式出现，称为**量子（quantum / quanta）**

![第 6 张：加热物体发光的黑体辐射现象](figures/CHM1001W1-Electronic-Structure/slide-06.png)

![第 7 张：能量量子化的示意（能量以 quanta 形式放出）](figures/CHM1001W1-Electronic-Structure/slide-07.png)

- **光电效应（photoelectric effect）**：Einstein 用量子解释
- 每种金属都有各自的**逸出能量阈值**；低于该能量**不发射**电子
- 结论：**能量与频率成正比**　$E = h\nu$　`[待核实]` 提取文本作 `E = h`（ν 丢失）
- **Planck 常数** $h = 6.626\times10^{-34}\ \mathrm{J\cdot s}$

![第 8 张：光电效应——能量高于阈值才逸出电子，E = hν](figures/CHM1001W1-Electronic-Structure/slide-08.png)

---

## 4. 原子光谱：连续谱 vs 线状谱（Atomic Emissions / Continuous vs. Line Spectra）

- 另一个谜题：原子与分子发出的**发射光谱**
- 原子/分子**不**给出连续谱（"彩虹"），只给出**若干离散波长**的**线状谱**
- **每种元素有唯一的线状谱**（可作为元素指纹）

![第 9 张：原子发射光谱的产生](figures/CHM1001W1-Electronic-Structure/slide-09.png)

![第 10 张：连续谱（白光源）与线状谱（原子）的对比](figures/CHM1001W1-Electronic-Structure/slide-10.png)

### 氢光谱（The Hydrogen Spectrum）

- **Johann Balmer（1885）**：发现把 4 条谱线联系到整数的简单公式
- **Johannes Rydberg**：把该公式推广
- **Niels Bohr**：解释了这条数学关系**为什么成立**　<u>公式在图内</u>

![第 11 张：氢原子线状谱与 Balmer/Rydberg 公式](figures/CHM1001W1-Electronic-Structure/slide-11.png)

---

## 5. Bohr 模型

三条基本假设：

1. 原子中的电子**只能占据特定轨道**（对应特定能量）
2. 处在**允许轨道**上的电子具有特定的"允许"能量，**不会辐射能量**
3. 能量只在电子**从一个允许态跃迁到另一个允许态**时被吸收或放出，由 $E = h\nu$ 决定　`[待核实]` 提取文本作 `E = h`（ν 丢失）

![第 12 张：Bohr 模型的定态轨道](figures/CHM1001W1-Electronic-Structure/slide-12.png)

![第 13 张：允许能级与跃迁吸放能 E = hν](figures/CHM1001W1-Electronic-Structure/slide-13.png)

- **跃迁能计算式**：电子被激发/回落时吸收或放出的能量可用一个含 **Rydberg 常数**的公式算出
- **Rydberg 常数** $R_H = 1.097\times10^{7}\ \mathrm{m^{-1}}$
- $n_i$、$n_f$ 分别为电子的**初始**与**末态**能级　<u>公式在图内</u>

![第 14 张：电子跃迁吸放能的计算公式与 Rydberg 常数](figures/CHM1001W1-Electronic-Structure/slide-14.png)

### Bohr 模型的局限

- **只对氢原子有效**
- 经典物理下电子应坠入带正电的原子核，Bohr 只是**假设**它不会
- 圆周运动在本质上并**不是波动**的

### 被后续模型保留的两个观点（Important Ideas from the Bohr Model）

1. 电子只存在于**某些离散能级**
2. 电子在能级间跃迁时**涉及能量的变化**

---

## 6. 物质波与量子力学（The Wave Nature of Matter / Quantum Mechanics）

- **de Broglie**：既然光具有物质属性，**物质也应具有波的属性**
- 质量与波长的关系式　<u>公式在图内</u>
- 光的波动性被用来产生电子显微图（electron micrograph）

![第 17 张：de Broglie 关系式与电子显微图](figures/CHM1001W1-Electronic-Structure/slide-17.png)

- **Heisenberg 不确定性原理**：粒子的**动量**测得越准，**位置**就越不准　<u>公式在图内</u>

![第 18 张：Heisenberg 不确定性原理](figures/CHM1001W1-Electronic-Structure/slide-18.png)

- **Schrödinger**：建立了一套同时容纳物质**波性**与**粒性**的数学处理方法 —— 即**量子力学**
- 波方程的解记作希腊字母 **ψ (psi)**
- **ψ 的平方（ψ²）**给出**电子密度**，即某时刻电子最可能出现在哪里的概率　`[待核实]` 提取文本作 "2"（上标丢失），应为 ψ²

![第 19 张：Schrödinger 方程与量子力学](figures/CHM1001W1-Electronic-Structure/slide-19.png)

![第 20 张：ψ 与其平方 ψ²（电子密度/概率分布）](figures/CHM1001W1-Electronic-Structure/slide-20.png)

---

## 7. 量子数（Quantum Numbers）

- 解波方程得到一组**波函数（即轨道）**及对应能量
- 每个轨道描述一种**电子密度的空间分布**
- 一个轨道由**三个量子数**描述

### 主量子数 n（Principal Quantum Number, n）

- 描述轨道所在的**能级**
- 取整数 $n \ge 1$，与 Bohr 模型中的取值对应

### 角动量量子数 l（Angular Momentum Quantum Number, l）

- 决定轨道的**形状**
- 取值范围：$0$ 到 $n-1$ 的整数
- 用**字母记号**表示不同的 l 值（即轨道的形状与类型）

![第 24 张：l 的字母记号与对应的轨道形状](figures/CHM1001W1-Electronic-Structure/slide-24.png)

### 磁量子数 ml

- 描述轨道的**三维取向**
- 取值范围：$-l \le m_l \le l$
- 因此在任一能级上，最多可有 **1 个 s、3 个 p、5 个 d、7 个 f 轨道**，依此类推

### 壳层与亚层（Electron Shell / Subshell）

- 同一个 $n$ 的轨道构成一个**电子壳层（shell）**
- 壳层内不同轨道类型构成**亚层（subshell）**

![第 26 张：壳层与亚层的层级关系](figures/CHM1001W1-Electronic-Structure/slide-26.png)

### 自旋量子数 ms

- 1920 年代发现：**同一轨道内的两个电子能量并不完全相同**
- 电子的"**自旋**"描述其磁场，进而影响能量 → 引出**自旋量子数 ms**
- ms 只有两个允许值：**+½ 与 −½**

![第 34 张：电子自旋与 ms = ±½](figures/CHM1001W1-Electronic-Structure/slide-34.png)

---

## 8. 轨道的形状（s / p / d / f Orbitals）

### s 轨道（l = 0 / s Orbitals）

- **球形**
- 球的半径随 n 增大而增大

![第 27 张：s 轨道的球形电子密度](figures/CHM1001W1-Electronic-Structure/slide-27.png)

- 对 **ns 轨道**：**峰（peaks）数 = n**
- 对 **ns 轨道**：**节点（nodes，电子出现概率为零处）数 = n − 1**
- n 越大，电子密度越"铺开"，电子出现在**离核更远**处的概率越大

![第 28 张：ns 轨道的峰数与节点数（n 与 n−1）](figures/CHM1001W1-Electronic-Structure/slide-28.png)

### p 轨道（l = 1 / p Orbitals）

- 有**两个瓣（lobes）**，中间夹一个**节点**

![第 29 张：p 轨道的双瓣结构](figures/CHM1001W1-Electronic-Structure/slide-29.png)

### d 轨道（l = 2 / d Orbitals）

- 五个 d 轨道中**四个有四个瓣**；另一个形似 p 轨道**中间套一个甜甜圈（doughnut）**

![第 30 张：五种 d 轨道的形状](figures/CHM1001W1-Electronic-Structure/slide-30.png)

### f 轨道（l = 3 / f Orbitals）

- 形状非常复杂（教材未给出）
- 一个亚层内有**七个等价轨道**

---

## 9. 轨道的能量（Energies of Orbitals）

### 氢原子（单电子 / Energies of Orbitals—Hydrogen）

- 同一能级上的各轨道**能量相同** —— 化学上称为**简并轨道（degenerate orbitals）**

![第 32 张：氢原子中同层轨道简并](figures/CHM1001W1-Electronic-Structure/slide-32.png)

### 多电子原子（Energies of Orbitals—Many-electron Atoms）

- 电子数增多 → **电子间排斥**增强
- 因此多电子原子中，**同一能级上的轨道不再全部简并**
- 但**同一亚层内的轨道组仍简并**
- 能级开始**交错**：例如 **4s 的能量低于 3d**

![第 33 张：多电子原子的能级交错（4s 低于 3d）](figures/CHM1001W1-Electronic-Structure/slide-33.png)

---

## 10. Pauli 不相容原理

- **同一原子中，没有两个电子可以具有完全相同的一组量子数**
- 即每个电子至少要在 n、l、ml、ms 四个值中**有一个不同**

---

## 11. 电子排布（Electron Configurations）

- **电子构型**：电子在原子中的分布方式
- 最稳定的排布是能量最低者，称为**基态（ground state）**
- 每个组成部分的含义（以 $4p^5$ 为例）：

| 成分 | 含义 | 例（4p⁵） |
|:--|:--|:--|
| 数字 | 能级 | 4 |
| 字母 | 轨道类型 | p |
| 上标 | 该轨道中的电子数 | 5 |

### 轨道图（Orbital Diagrams）

- 图中**每个方框 = 一个轨道**
- **半箭头 = 一个电子**
- **箭头方向 = 电子的相对自旋**

![第 39 张：轨道图的画法（方框、半箭头、自旋方向）](figures/CHM1001W1-Electronic-Structure/slide-39.png)

### Hund 规则

> "对简并轨道，当**自旋相同的电子数取最大**时，能量最低。"

- 即：同一亚层的一组轨道上，**先每个轨道各放一个电子且自旋相同**，然后才配对

![第 40 张：Hund 规则的排布示例](figures/CHM1001W1-Electronic-Structure/slide-40.png)

### 简写构型（Condensed）

- 同一**族**的元素最外层电子数相同 —— 这些是**价电子（valence electrons）**
- 内层已充满的电子称为**芯电子（core electrons）**，包括完全充满的 d 或 f 亚层
- 写法：用**方括号括起的稀有气体符号** + 只列出**价电子**

![第 41 张：简写电子构型的写法](figures/CHM1001W1-Electronic-Structure/slide-41.png)

### 周期表与轨道填充（Periodic Table）

- 轨道按**能量递增**顺序填充
- 周期表上不同区块对应不同轨道类型：
  - **s = 蓝色**、**p = 粉色**（s、p 为主族元素 / representative elements）
  - **d = 橙色**（过渡元素）
  - **f = 棕褐色**（镧系与锕系，即内过渡元素）

![第 42 张：周期表分区与轨道类型对应（s/p/d/f）](figures/CHM1001W1-Electronic-Structure/slide-42.png)

### 异常（Anomalies）

- 当电子数足以**半充满同一行的 s 与 d 轨道**时，会出现不规则

![第 43 张：电子构型的异常情形](figures/CHM1001W1-Electronic-Structure/slide-43.png)

- **铬（Cr）**的例子：
  - 实际：$[\mathrm{Ar}]\,4s^1 3d^5$
  - 预期：$[\mathrm{Ar}]\,4s^2 3d^4$
- 原因：**4s 与 3d 的能量非常接近**
- f 区原子的 f 与 d 轨道也有类似异常

### 为什么 4s 先填、电离时却先失电子？（Why 4s Subshell Is Filled Before 3d）

> **规则**：轨道的**填充**取决于**轨道能量**；电子的**移去**取决于**轨道位置（location）**。

- **4s 能量低于 3d** → 所以**先填 4s**
- **4s 离核比 3d 更远** → 所以**电离时先失 4s 电子**

---

## 关键术语

| 术语（English） | 释义 |
|:--|:--|
| wavelength（波长，λ） | 相邻对应点之间的距离 |
| frequency（频率，ν） | 单位时间通过定点的波数 |
| quantum / quanta（量子） | 能量的最小"份额" |
| Planck's constant（Planck 常数，h） | $6.626\times10^{-34}\ \mathrm{J\cdot s}$ |
| photoelectric effect（光电效应） | 光照射金属逸出电子；低于阈值不发射 |
| continuous / line spectrum（连续谱 / 线状谱） | 原子只给离散波长的线状谱 |
| Rydberg constant（Rydberg 常数，$R_H$） | $1.097\times10^{7}\ \mathrm{m^{-1}}$ |
| degenerate orbitals（简并轨道） | 能量相同的轨道 |
| shell / subshell（壳层 / 亚层） | 同 n 的轨道组 / 壳层内的轨道类型组 |
| ground state（基态） | 能量最低的最稳定排布 |
| valence / core electrons（价电子 / 芯电子） | 最外层电子 / 内层已充满的电子 |
| orbital diagram（轨道图） | 方框+半箭头表示轨道与电子自旋 |

## 易错点 / 待核实

- `[待核实]` **多处公式在提取文本中丢失了符号或上标**（原公式是图片或特殊字符）：
  - 第 5 张：仅有 `c =`，缺 λ、ν
  - 第 8、13 张：`E = h`，缺 ν
  - 第 11 张：Balmer/Rydberg 公式整体丢失
  - 第 14 张：跃迁能计算式丢失（仅保留了 $R_H$ 与 $n_i$、$n_f$ 的说明）
  - 第 17 张：de Broglie 关系式丢失
  - 第 18 张：不确定性关系式丢失
  - 第 20 张：`ψ²` 的上标丢失，文本作 "2"
  → **以上各处请直接看对应插图的原式**，本笔记未据记忆补写。
- 第 16 张正文编号只出现了 `2)`，**第 1 点疑似在提取时丢编号**（内容是"电子只存在于某些离散能级"）。
- 第 36/37/38 三张内容几乎相同，是**同一条要点逐步补全**的过程（数字 → 字母 → 上标），不是三个独立知识点。
- 第 15 张明确指出 Bohr 模型**只适用于氢**，不要外推到多电子原子。

## 出处索引

| 小节 | 对应张次 |
|:--|:--|
| 1 为什么从波讲起 | 1–2 |
| 2 电磁波基础 | 3–5 |
| 3 能量量子化 | 6–8 |
| 4 原子光谱 | 9–11 |
| 5 Bohr 模型（含局限与保留观点） | 12–16 |
| 6 物质波与量子力学 | 17–20 |
| 7 量子数（n / l / ml / 壳层亚层 / ms） | 21–26、34–35 |
| 8 轨道形状（s / p / d / f） | 27–31 |
| 9 轨道能量（氢 / 多电子） | 32–33 |
| 10 Pauli 不相容原理 | 35 |
| 11 电子排布（含 Hund、简写、周期表、异常） | 36–45 |

---

*本笔记内容全部来自 `_System/extracted/CHM1001W1-Electronic Structure.slides.txt` 的逐张提取文本（45 张）。插图由脚本以 150 dpi 整页渲染，未做美化或重绘。凡提取文本中丢失的公式均已在下文标出并在文末汇总，未据记忆补写。*

---

## 公式在图内（提取文本丢失）

- 第 11 张：公式在图内、提取文本丢失（Balmer / Rydberg 公式整体丢失）
- 第 14 张：公式在图内、提取文本丢失（跃迁能计算式丢失，仅保留 $R_H$ 与 $n_i$、$n_f$ 的说明）
- 第 17 张：公式在图内、提取文本丢失（de Broglie 关系式丢失）
- 第 18 张：公式在图内、提取文本丢失（不确定性关系式丢失）
