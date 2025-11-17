# EVE SDE Build 3096543.02 - 版本比较报告

**构建时间**: 2025-11-17 03:05:06

## 图标文件比较

**文件统计**:
- 当前版本: 10097 个文件
- 旧版本: 10097 个文件
- 新增: 0 个文件
- 删除: 0 个文件
- 共同: 10097 个文件

## 数据库比较

### EN 数据库

**数据库差异**:
```sql
UPDATE version_info SET patch_number=2 WHERE id=1;
```

### ZH 数据库

**数据库差异**:
```sql
UPDATE version_info SET patch_number=2 WHERE id=1;
```

## 地图和本地化文件比较

### regions_data.json

文件无差异

### systems_data.json

文件无差异

### neighbors_data.json

文件无差异

## 本地化文件比较

### accountingentrytypes_localized.json

**文件差异**:
```diff
--- /tmp/tmp2fc79qba/sde_old/localization/accountingentrytypes_localized.json
+++ /home/runner/work/EveSDE_2.0/EveSDE_2.0/output_sde/localization/accountingentrytypes_localized.json
@@ -1463,6 +1463,14 @@
       "zh": [

         "行星进口税"

       ]

+    },

+    "entryJournalMessage": {

+      "en": [

+        "Planetary Import Tax: {name1} imported to {location}"

+      ],

+      "zh": [

+        "行星进口税: 由 {name1} 进口到 {location}"

+      ]

     }

   },

   "planetary_export_tax": {

@@ -1472,6 +1480,14 @@
       ],

       "zh": [

         "行星出口税"

+      ]

+    },

+    "entryJournalMessage": {

+      "en": [

+        "Planetary Export Tax: {name1} exported from {location}"

+      ],

+      "zh": [

+        "行星出口税: 由 {name1} 从 {location} 出口"

       ]

     }

   },

```


## 下载文件

- **icons.zip**: 图标压缩包
- **sde.zip**: SDE数据压缩包
- **release_compare_3096543.02.md**: 详细比较报告
