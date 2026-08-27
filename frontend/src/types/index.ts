export interface Monitor {
  id: string;
  name: string;
  asin: string;
  original_url: string;
  url: string;
  image_url?: string;
  target_price: number;
  current_price?: number;
  previous_price?: number;
  lowest_price?: number;
  highest_price?: number;
  check_interval: number;
  is_active: boolean;
  alert_triggered: boolean;
  use_default_webhook: boolean;
  discord_webhook?: string;
  availability: boolean;
  status: 'monitoring' | 'target_reached' | 'paused' | 'out_of_stock' | 'error';
  last_checked_at?: string;
  next_check_at?: string;
  last_error?: string;
  last_error_at?: string;
  created_at: string;
  updated_at: string;
}

export interface Settings {
  discord_webhook?: string;
  default_check_interval: number;
  theme: 'light' | 'dark';
  currency: string;
}

export interface HistoryEntry {
  price?: number;
  available: boolean;
  checked_at: string;
}

export interface ProductTestResponse {
  title: string;
  price?: number;
  image_url?: string;
  availability: boolean;
  asin: string;
  url: string;
}
