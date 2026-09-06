# AI 病害识别适配接口建议

## 推荐调用链

`Vue Web → Java任务服务 → 算法适配层 → 识别/分割模型 → 分级规则服务 → 病害档案`

Demo 当前在浏览器内模拟该过程。正式平台应改为异步任务，图片上传后立即返回任务 ID，前端通过事件推送或轮询获取进度。

## 创建诊断任务

`POST /api/v1/diagnosis/tasks`

表单字段：

- `image`：原始检查图片
- `tunnelId`：已确认的隧道实体 ID
- `inspectionTaskId`：巡检任务 ID，可选
- `captureTime`：拍摄时间，可选
- `chainage`：隧道桩号，可选
- `calibrationId`：尺寸标定参数，可选

返回：

```json
{
  "taskId": "DX-20260904-001",
  "status": "queued",
  "tunnelId": "SX-TUN-0007"
}
```

## 统一诊断结果

`GET /api/v1/diagnosis/tasks/{taskId}`

```json
{
  "taskId": "DX-20260904-001",
  "status": "completed",
  "tunnelId": "SX-TUN-0007",
  "imageQuality": {
    "passed": true,
    "issues": []
  },
  "findings": [
    {
      "findingId": "F-001",
      "typeCode": "LINING_CRACK",
      "typeName": "衬砌裂缝",
      "confidence": 0.916,
      "geometry": {
        "type": "polygon",
        "normalizedPoints": [[0.16, 0.12], [0.47, 0.12], [0.47, 0.51], [0.16, 0.51]]
      },
      "measurements": {
        "lengthM": 1.34,
        "widthMm": 0.82,
        "calibrated": true
      },
      "location": {
        "part": "左拱腰",
        "chainage": "K0+236"
      },
      "severity": {
        "grade": "III",
        "label": "重点处置",
        "ruleIds": ["CRACK-WIDTH-03"]
      }
    }
  ],
  "decision": {
    "requiresHumanReview": true,
    "reviewDeadlineHours": 24,
    "actions": [
      "现场复测裂缝宽度与长度",
      "核查渗漏水来源",
      "根据复核结论制定维修计划"
    ]
  },
  "model": {
    "name": "Tunnel-Crack",
    "version": "2.4.0"
  }
}
```

## 关键约束

- 识别置信度与病害等级必须分字段存储和展示。
- 没有标尺、相机标定或三维重建条件时，不应输出毫米级真实测量结论。
- 隧道内部影像通常缺少可靠 GPS，必须通过巡检任务、设备轨迹、桩号或人工选择完成实体绑定。
- 原图、标注结果、模型版本、规则版本和人工复核意见需要共同归档，保证诊断结论可追溯。
