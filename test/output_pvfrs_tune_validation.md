# PVFRS 改进回测 - 参数调优结果

## 参数网格

```json
{
  "stop_loss": [
    -0.06,
    -0.1
  ],
  "take_profit": [
    0.15,
    0.25
  ],
  "max_holding_days": [
    30,
    60
  ]
}
```

## 最佳参数

```json
{
  "stop_loss": -0.1,
  "take_profit": 0.25,
  "max_holding_days": 30
}
```

## 最佳绩效

- **total_return**: 0.018919
- **annual_return**: 0.009806
- **max_drawdown**: 0.01019
- **sharpe_ratio**: -1.642206
- **win_rate**: 0.666667
- **profit_factor**: 5.755319
- **total_trades**: 3
- **winning_trades**: 2
- **losing_trades**: 1
- **avg_holding_period**: 30.0
- **initial_capital**: 100000
- **final_capital**: 101891.91265575001
- **start_date**: 2023-01-01
- **end_date**: 2024-12-31
- **symbols_count**: 3

## 全部组合结果

### 组合 1

```json
{
  "stop_loss": -0.06,
  "take_profit": 0.15,
  "max_holding_days": 30
}
```

- total_return: 0.00518
- annual_return: 0.002694
- max_drawdown: 0.017142
- sharpe_ratio: -2.308198
- win_rate: 0.4
- profit_factor: 1.210757
- total_trades: 5
- winning_trades: 2
- losing_trades: 3
- avg_holding_period: 15.2
- initial_capital: 100000
- final_capital: 100518.033304412
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 2

```json
{
  "stop_loss": -0.06,
  "take_profit": 0.15,
  "max_holding_days": 60
}
```

- total_return: 0.005488
- annual_return: 0.002854
- max_drawdown: 0.017142
- sharpe_ratio: -2.143867
- win_rate: 0.4
- profit_factor: 1.22624
- total_trades: 5
- winning_trades: 2
- losing_trades: 3
- avg_holding_period: 21.2
- initial_capital: 100000
- final_capital: 100548.773299646
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 3

```json
{
  "stop_loss": -0.06,
  "take_profit": 0.25,
  "max_holding_days": 30
}
```

- total_return: 0.009294
- annual_return: 0.004828
- max_drawdown: 0.017142
- sharpe_ratio: -2.132516
- win_rate: 0.5
- profit_factor: 1.63022
- total_trades: 4
- winning_trades: 2
- losing_trades: 2
- avg_holding_period: 19.0
- initial_capital: 100000
- final_capital: 100929.364001215
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 4

```json
{
  "stop_loss": -0.06,
  "take_profit": 0.25,
  "max_holding_days": 60
}
```

- total_return: -0.011077
- annual_return: -0.005783
- max_drawdown: 0.02859
- sharpe_ratio: -2.564269
- win_rate: 0.25
- profit_factor: 0.396925
- total_trades: 4
- winning_trades: 1
- losing_trades: 3
- avg_holding_period: 34.5
- initial_capital: 100000
- final_capital: 98892.26063212201
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 5

```json
{
  "stop_loss": -0.1,
  "take_profit": 0.15,
  "max_holding_days": 30
}
```

- total_return: 0.009171
- annual_return: 0.004764
- max_drawdown: 0.016135
- sharpe_ratio: -1.987828
- win_rate: 0.5
- profit_factor: 1.528299
- total_trades: 4
- winning_trades: 2
- losing_trades: 2
- avg_holding_period: 23.75
- initial_capital: 100000
- final_capital: 100917.05913971101
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 6

```json
{
  "stop_loss": -0.1,
  "take_profit": 0.15,
  "max_holding_days": 60
}
```

- total_return: 0.002537
- annual_return: 0.00132
- max_drawdown: 0.017
- sharpe_ratio: -2.087715
- win_rate: 0.5
- profit_factor: 1.077044
- total_trades: 4
- winning_trades: 2
- losing_trades: 2
- avg_holding_period: 34.75
- initial_capital: 100000
- final_capital: 100253.652865232
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 7

```json
{
  "stop_loss": -0.1,
  "take_profit": 0.25,
  "max_holding_days": 30
}
```

- total_return: 0.018919
- annual_return: 0.009806
- max_drawdown: 0.01019
- sharpe_ratio: -1.642206
- win_rate: 0.666667
- profit_factor: 5.755319
- total_trades: 3
- winning_trades: 2
- losing_trades: 1
- avg_holding_period: 30.0
- initial_capital: 100000
- final_capital: 101891.91265575001
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3

### 组合 8

```json
{
  "stop_loss": -0.1,
  "take_profit": 0.25,
  "max_holding_days": 60
}
```

- total_return: -0.008484
- annual_return: -0.004426
- max_drawdown: 0.02853
- sharpe_ratio: -2.350824
- win_rate: 0.333333
- profit_factor: 0.463268
- total_trades: 3
- winning_trades: 1
- losing_trades: 2
- avg_holding_period: 55.333333
- initial_capital: 100000
- final_capital: 99151.62707631601
- start_date: 2023-01-01
- end_date: 2024-12-31
- symbols_count: 3
