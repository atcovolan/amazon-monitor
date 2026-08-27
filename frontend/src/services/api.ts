import type { Monitor, Settings, HistoryEntry, ProductTestResponse } from '../types';

const API_BASE = '/api';

export async function fetchSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error('Falha ao buscar configurações');
  return res.json();
}

export async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error('Falha ao atualizar configurações');
  return res.json();
}

export async function fetchProducts(): Promise<Monitor[]> {
  const res = await fetch(`${API_BASE}/products`);
  if (!res.ok) throw new Error('Falha ao obter monitores');
  return res.json();
}

export async function fetchProductDetail(id: string): Promise<Monitor> {
  const res = await fetch(`${API_BASE}/products/${id}`);
  if (!res.ok) throw new Error('Falha ao obter detalhes do monitor');
  return res.json();
}

export async function createProduct(product: {
  url: string;
  target_price: number;
  check_interval: number;
  use_default_webhook: boolean;
  discord_webhook?: string;
  name?: string;
}): Promise<Monitor> {
  const res = await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(product),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Falha ao criar monitor');
  }
  return res.json();
}

export async function updateProduct(id: string, product: Partial<Monitor>): Promise<Monitor> {
  const res = await fetch(`${API_BASE}/products/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(product),
  });
  if (!res.ok) throw new Error('Falha ao atualizar monitor');
  return res.json();
}

export async function deleteProduct(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/products/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Falha ao excluir monitor');
}

export async function testProduct(url: string): Promise<ProductTestResponse> {
  const res = await fetch(`${API_BASE}/products/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Falha ao testar produto');
  }
  return res.json();
}

export async function checkProductNow(id: string): Promise<Monitor> {
  const res = await fetch(`${API_BASE}/products/${id}/check`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Falha ao verificar agora');
  return res.json();
}

export async function pauseProduct(id: string): Promise<Monitor> {
  const res = await fetch(`${API_BASE}/products/${id}/pause`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Falha ao pausar monitor');
  return res.json();
}

export async function resumeProduct(id: string): Promise<Monitor> {
  const res = await fetch(`${API_BASE}/products/${id}/resume`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Falha ao retomar monitor');
  return res.json();
}

export async function fetchProductHistory(id: string): Promise<HistoryEntry[]> {
  const res = await fetch(`${API_BASE}/products/${id}/history`);
  if (!res.ok) throw new Error('Falha ao buscar histórico');
  return res.json();
}
