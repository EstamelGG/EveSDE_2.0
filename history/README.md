# Release比对记录历史

此目录包含每次SDE构建的详细比对记录。

## 文件命名规则

`release_compare_{BUILD_NUMBER}.md`

例如：
- `release_compare_3049853.01.md` - Build 3049853 补丁版本 01
- `release_compare_3049853.md` - Build 3049853

## 自动生成

这些文件由 GitHub Actions 自动生成并提交到此目录。

每次构建完成后，比对记录会：
1. 作为 Release 附件上传
2. 自动提交到此 history 目录以便历史追踪

