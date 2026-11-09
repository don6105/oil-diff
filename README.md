<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="oil-diff：將零散的 Git 變更整理成容易理解的視覺化報告頁。">
</p>

本專案由 [oil-oil/oil-diff](https://github.com/oil-oil/oil-diff) 翻譯為**繁體中文**，並依個人習慣調整 UI 介面。

- 專案網址：[don6105/oil-diff](https://github.com/don6105/oil-diff)。

- `oil-diff` 是將 Git 變更整理成視覺化報告的 Skill。
- 它會依業務目的，將工作區修改、某次提交或分支之間的差異整理成 **3～7 件具體事項**。
- 產生的 HTML 報告頁位於 `.oil-diff/index.html`。
- 適合向團隊說明變更、合併程式碼前檢查全貌，或快速了解人工智慧剛才修改了哪些內容。
  - 開啟網頁即可查看業務範圍、修改原因，以及需要優先檢查的檔案。

<p align="center">
  <img src="./assets/readme/before-after.svg" width="100%" alt="比較直接閱讀 Git 差異與使用 oil-diff 視覺化報告頁的差別。">
</p>

## 核心功能

<p align="center">
  <img src="./assets/readme/section-features.svg" width="100%" alt="核心功能：依業務目的說明變更，搭配圖示與程式碼抽屜。">
</p>

### 1. 以 Bento 看板整理業務變更

- 將整批修改整理成業務卡片，不必逐一翻閱檔案清單。
- 頁面頂端提供模組導覽。
- 每張卡片說明原本的問題與目前的處理方式。

<p align="center">
  <img src="./assets/readme/case-overview.png?v=zh-tw-2" width="100%" alt="oil-diff 頁面總覽與右側變更檔案樹。">
</p>

### 2. 圖示與文字各自說明重點

- 每一章都提供修改前後的比較圖。
- **介面變更**：可放入實際執行時擷取的畫面。
  - 拖曳滑桿比較修改前後的差異，或點選放大。
- **邏輯或規則變更**：可產生路由分流圖、控制項比較圖、流程圖或欄位增刪表。

<p align="center">
  <img src="./assets/readme/case-diagram-routing.png?v=zh-tw-2" width="100%" alt="章節圖示範例：將複雜規則拆成容易理解的分流結構。">
</p>

### 3. 區分「🎯 核心必看」與「📎 周邊同步」

- **🎯 核心必看**：依章節中的具體變更要點分類。
  - 標示新增與刪除行數，方便審查時優先查看核心檔案。
- **📎 周邊同步**：收納同步修改的引用、設定與文件。
  - 預設摺疊於卡片底部，保留完整範圍並減少畫面干擾。

### 4. 可收合的檔案樹與可調整寬度的程式碼抽屜

- 右側提供變更檔案樹，可一鍵收合以增加閱讀空間。
- 點選核心檔案標籤或檔案樹，即可開啟右側的程式碼抽屜。
  - 抽屜顯示修改前後的原文對照。
  - 主頁面的高度與捲動位置維持不變。
- 拖曳抽屜左側邊緣即可調整寬度。
  - 瀏覽器會記住寬度，再次開啟時沿用。

<p align="center">
  <img src="./assets/readme/case-drawer.png?v=zh-tw-2" width="100%" alt="點選檔案後，從右側開啟修改前後的程式碼對照抽屜。">
</p>

## 安裝與使用

<p align="center">
  <img src="./assets/readme/section-use.svg" width="100%" alt="安裝與使用：將儲存庫或分支交給 Agent 處理。">
</p>

### 安裝

- **方式一：命令列安裝**
  - 安裝本專案的繁體中文版。

```bash
npx skills add don6105/oil-diff
```

- **方式二：請 Agent 安裝**

```text
請幫我安裝這個 Skill：https://github.com/don6105/oil-diff
```

### 日常使用

- 安裝後，直接在對話中指定要查看的變更範圍。

```text
用 oil-diff 將目前分支最近的變更做成報告頁。
```

```text
用 oil-diff 整理目前尚未提交的修改，產生一份 HTML 變更報告。
```

```text
用 oil-diff 比較 main..HEAD 的差異，說明這次修改了哪些事項。
```

## 適用範圍、資料與執行環境

- **不影響儲存庫狀態**：產生的網頁與資料都放在 `<repo>/.oil-diff/`。
  - 該目錄會自動被 Git 忽略。
  - 不修改目標專案的既有檔案，也不影響 `git status`。
- **單一檔案可離線使用**：`.oil-diff/index.html` 不依賴外部資源。
  - 按兩下即可在瀏覽器開啟，也可以直接傳給同事。
- **設定與相容性**：僅依賴系統的 `git` 與 Python 3.10+ 標準函式庫。
  - 不需要額外設定金鑰或環境變數。
  - 支援 macOS、Windows 與 Linux。

<p align="center">
  <a href="https://github.com/oil-oil/beautify-github-readme"><img src="./assets/readme/made-with-beautify.svg" width="300" alt="README 使用 beautify-github-readme 製作。"></a>
</p>

## 授權條款

- MIT License
