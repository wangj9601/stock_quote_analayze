-- 为 gms_signal_trace 表添加得分明细字段
-- 若表已存在，执行以下 ALTER 语句

ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS score_acc_fz real;
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS score_acc_balance real;
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS score_acc_volume real;
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS score_mom_ratio_d1 real;
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS score_mom_deviation real;
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS score_mom_volume real;
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS acc_fz_judge character varying(50);
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS acc_balance_judge character varying(50);
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS acc_volume_judge character varying(50);
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS mom_ratio_d1_judge character varying(50);
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS mom_deviation_judge character varying(50);
ALTER TABLE public.gms_signal_trace ADD COLUMN IF NOT EXISTS mom_volume_judge character varying(50);
