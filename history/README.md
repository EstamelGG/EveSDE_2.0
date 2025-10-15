# Release比对记录历史

此目录包含每次SDE构建的详细比对记录。

## 文件命名规则

`release_compare_{BUILD_NUMBER}_{TIMESTAMP}.md`

- `BUILD_NUMBER`: SDE构建版本号（可能包含补丁版本，如 `3049853.01`）
- `TIMESTAMP`: UTC时间戳，格式为 `YYYYMMDD_HHMMSS`

例如：
- `release_compare_3049853.01_20251015_083045.md` - Build 3049853.01，生成于2025-10-15 08:30:45 UTC
- `release_compare_3049853_20251015_120000.md` - Build 3049853，生成于2025-10-15 12:00:00 UTC

## 自动生成

这些文件由 GitHub Actions 自动生成并提交到此目录。

每次构建完成后，比对记录会：
1. 自动提交到此 history 目录以便历史追踪
2. 在 Release 说明中提供查看链接

## 时间戳说明

使用时间戳的原因：
- 防止同一build number多次运行时文件覆盖
- 保留完整的构建历史
- 便于按时间顺序查看记录

