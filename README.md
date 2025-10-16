# tips 模块（个性化体检前提示 Agent）

## 接口
- POST `/api/v1/tips/personalized_batch`
  - 入参（批量）：
```json
{
  "user_id": "org_001",
  "persons": [
    {
      "name": "张三",
      "phone": "13800000000",
      "age": 45,
      "gender": "male",
      "appointment_date": "2025-10-16",
      "check_items": ["心电图","腹部彩超","前列腺彩超"],
      "chronic_conditions": ["高血压"],
      "marital_status": "已婚"
    }
  ]
}
```
  - 出参：
```json
{
  "trace_id": "req_xxxxxx",
  "status": "success",
  "timestamp": "2025-10-16T10:00:00+08:00",
  "data": {
    "user_id": "org_001",
    "reminders": [
      {
        "name": "张三",
        "phone": "13800000000",
        "messages": ["..."],
        "text": "- ...\n- ..."
      }
    ]
  }
}
```

## 运行
- 独立启动（推荐）
```bash
conda activate agent_chat
uvicorn tips.main:app --host 127.0.0.1 --port 8002 --reload
```
- 健康检查：GET `http://127.0.0.1:8002/health`

### 自测示例（CMD）
- 单行：
```bash
curl -X POST "http://127.0.0.1:8002/api/v1/tips/personalized_batch" -H "Content-Type: application/json" -d "{\"user_id\":\"org_001\",\"persons\":[{\"name\":\"张三\",\"gender\":\"male\",\"age\":45,\"appointment_date\":\"2025-10-16\",\"check_items\":[\"心电图\",\"腹部彩超\",\"前列腺彩超\"],\"chronic_conditions\":[\"高血压\"]}]}"
```
- 多行（使用 ^ 续行）：
```bash
curl -X POST "http://127.0.0.1:8002/api/v1/tips/personalized_batch" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"org_001\",\"persons\":[{\"name\":\"张三\",\"gender\":\"male\",\"age\":45,\"appointment_date\":\"2025-10-16\",\"check_items\":[\"心电图\",\"腹部彩超\",\"前列腺彩超\"],\"chronic_conditions\":[\"高血压\"]}]}"
```
- 使用文件（保存为 request.json）：
```json
{
  "user_id": "org_001",
  "persons": [
    {
      "name": "张三",
      "gender": "male",
      "age": 45,
      "appointment_date": "2025-10-16",
      "check_items": ["心电图", "腹部彩超", "前列腺彩超"],
      "chronic_conditions": ["高血压"]
    }
  ]
}
```
```bash
curl -X POST "http://127.0.0.1:8002/api/v1/tips/personalized_batch" -H "Content-Type: application/json" --data @request.json
```

## 说明
- 推荐仅使用 `/api/v1/tips/personalized_batch`；单人也按批量传（persons 仅1条）。
- 旧接口 `/api/v1/tips/personalized` 已标记废弃，仅保留兼容。