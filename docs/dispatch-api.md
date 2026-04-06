# Dispatch Service API 文档

## 1. 概览

- 服务名：`hsp-dispatch-service`
- HTTP Base Path：`/api/dispatch/v1`
- 健康检查：`GET /healthz`
- 协议：HTTP(JSON) + gRPC
- 时间字段格式：ISO-8601（例如 `2026-04-05T10:30:00+00:00`）

## 2. 业务状态约定

### 2.1 派单状态 `DispatchRecord.status`
- `PENDING`：已派单，待工人确认
- `ACCEPTED`：工人已接单
- `REJECTED`：工人已拒单

### 2.2 工人响应 `response`
- `ACCEPT`
- `REJECT`

## 3. 通用错误响应

HTTP 错误统一返回：

```json
{
  "detail": "error message"
}
```

常见错误码：
- `400` 参数或业务校验失败
- `404` 资源不存在
- `409` 业务状态冲突（如订单已有待确认派单）
- `503` 依赖服务不可用（order-service / worker-schedule-service）

## 4. HTTP API

### 4.1 查询可用工人

- 方法：`GET /workers/available`
- 说明：客服查询可派工人列表（实时查询 worker-schedule）

Query 参数：
- `service_type`（可选，string）
- `region`（可选，string）
- `at_time`（可选，datetime，ISO-8601）
- `limit`（可选，int，默认 `20`，范围 `1..100`）

成功响应 `200`：

```json
{
  "workers": [
    {
      "worker_id": "worker-001",
      "name": "Zhang San",
      "skills": ["cleaning", "moving"],
      "status": "AVAILABLE"
    }
  ]
}
```

---

### 4.2 手工派单

- 方法：`POST /dispatches/manual`
- 说明：客服将订单手动派给指定工人。operator_id 是 客服id。

请求体：

```json
{
  "order_id": "order-1001",
  "worker_id": "worker-001",
  "operator_id": "csr-001"
}
```

成功响应 `201`：

```json
{
  "dispatch_id": "6f88f9f2-65fd-4ef7-80de-2c96d8ab7b5b",
  "order_id": "order-1001",
  "attempt_no": 1,
  "worker_id": "worker-001",
  "operator_id": "csr-001",
  "status": "PENDING",
  "assigned_at": "2026-04-05T10:30:00+00:00",
  "responded_at": null,
  "reject_reason": null
}
```

可能错误：
- `400` 参数非法
- `404` 工人不存在
- `409` 订单已有 `PENDING` 派单，或工人不可用
- `503` 下游服务调用失败

---

### 4.3 查询工人待确认派单

- 方法：`GET /workers/{worker_id}/pending-dispatches`
- 说明：移动端轮询该工人的待确认派单

路径参数：
- `worker_id`（必填，string）

成功响应 `200`：

```json
{
  "dispatches": [
    {
      "dispatch_id": "6f88f9f2-65fd-4ef7-80de-2c96d8ab7b5b",
      "order_id": "order-1001",
      "attempt_no": 1,
      "worker_id": "worker-001",
      "operator_id": "csr-001",
      "status": "PENDING",
      "assigned_at": "2026-04-05T10:30:00+00:00",
      "responded_at": null,
      "reject_reason": null
    }
  ]
}
```

---

### 4.4 工人接单/拒单确认

- 方法：`POST /workers/{worker_id}/dispatches/{dispatch_id}/response`
- 说明：工人确认接单或拒单

路径参数：
- `worker_id`（必填，string）
- `dispatch_id`（必填，string）

请求体：

```json
{
  "response": "REJECT",
  "reject_reason": "busy with previous order"
}
```

规则：
- `response=ACCEPT` 时，`reject_reason` 必须为空
- `response=REJECT` 时，`reject_reason` 必填

成功响应 `200`：

```json
{
  "dispatch_id": "6f88f9f2-65fd-4ef7-80de-2c96d8ab7b5b",
  "order_id": "order-1001",
  "attempt_no": 1,
  "worker_id": "worker-001",
  "operator_id": "csr-001",
  "status": "REJECTED",
  "assigned_at": "2026-04-05T10:30:00+00:00",
  "responded_at": "2026-04-05T10:35:00+00:00",
  "reject_reason": "busy with previous order"
}
```

可能错误：
- `400` 参数非法或路径中的 `worker_id` 与派单不匹配
- `404` 派单不存在
- `409` 派单已响应，不能重复确认
- `503` 下游服务调用失败

---

### 4.5 查询订单派单历史

- 方法：`GET /orders/{order_id}/dispatch-history`
- 说明：查询订单全部派单尝试记录（满足可追踪）

路径参数：
- `order_id`（必填，string）

成功响应 `200`：

```json
{
  "dispatches": [
    {
      "dispatch_id": "id-1",
      "order_id": "order-1001",
      "attempt_no": 1,
      "worker_id": "worker-001",
      "operator_id": "csr-001",
      "status": "REJECTED",
      "assigned_at": "2026-04-05T10:30:00+00:00",
      "responded_at": "2026-04-05T10:35:00+00:00",
      "reject_reason": "busy"
    },
    {
      "dispatch_id": "id-2",
      "order_id": "order-1001",
      "attempt_no": 2,
      "worker_id": "worker-002",
      "operator_id": "csr-002",
      "status": "PENDING",
      "assigned_at": "2026-04-05T10:40:00+00:00",
      "responded_at": null,
      "reject_reason": null
    }
  ]
}
```

## 5. gRPC API

Proto 文件：`rpc/dispatch/v1/dispatch.proto`

Service：`dispatch.v1.DispatchService`

方法清单：
- `ListAvailableWorkers(ListAvailableWorkersRequest) returns (ListAvailableWorkersResponse)`
- `ManualAssignOrder(ManualAssignOrderRequest) returns (ManualAssignOrderResponse)`
- `ListWorkerPendingDispatches(ListWorkerPendingDispatchesRequest) returns (ListWorkerPendingDispatchesResponse)`
- `ConfirmWorkerResponse(ConfirmWorkerResponseRequest) returns (ConfirmWorkerResponseResponse)`
- `GetOrderDispatchHistory(GetOrderDispatchHistoryRequest) returns (GetOrderDispatchHistoryResponse)`

gRPC 错误码映射：
- `INVALID_ARGUMENT`：参数或业务校验失败
- `NOT_FOUND`：资源不存在
- `FAILED_PRECONDITION`：业务状态冲突
- `UNAVAILABLE`：依赖服务不可用

## 6. 跨模块交互边界（当前实现）

必须交互：
- `worker-schedule-service`：可用工人查询、占用工人、释放工人
- `order-service`：派单后状态更新、接单确认、拒单回待重派

不交互：
- `user-service`（`operator_id` 由请求传入）
- `payment-service`
- `execution-record-service`

## 7. 典型调用示例（HTTP）

### 7.1 手工派单

```bash
curl -X POST 'http://127.0.0.1:8080/api/dispatch/v1/dispatches/manual' \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id":"order-1001",
    "worker_id":"worker-001",
    "operator_id":"csr-001"
  }'
```

### 7.2 工人拒单

```bash
curl -X POST 'http://127.0.0.1:8080/api/dispatch/v1/workers/worker-001/dispatches/{dispatch_id}/response' \
  -H 'Content-Type: application/json' \
  -d '{
    "response":"REJECT",
    "reject_reason":"busy with previous order"
  }'
```
