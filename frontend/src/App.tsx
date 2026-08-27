import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  PlusCircle, 
  Settings as SettingsIcon, 
  TrendingDown, 
  AlertTriangle, 
  CheckCircle2, 
  Play, 
  Pause, 
  Trash2, 
  RefreshCw, 
  Eye, 
  ExternalLink,
  Sparkles,
  Search,
  Sun,
  Moon,
  Info,
  Clock,
  Activity
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ReferenceLine, 
  CartesianGrid 
} from 'recharts';
import { 
  fetchSettings, 
  updateSettings, 
  fetchProducts, 
  createProduct, 
  deleteProduct, 
  testProduct, 
  checkProductNow, 
  pauseProduct, 
  resumeProduct, 
  fetchProductHistory,
  updateProduct,
  fetchLogs 
} from './services/api';
import type { Monitor, Settings, HistoryEntry, ProductTestResponse, LogEntry } from './types';

// Simple toast implementation
interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'add' | 'settings'>('dashboard');
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [selectedMonitor, setSelectedMonitor] = useState<Monitor | null>(null);
  const [selectedHistory, setSelectedHistory] = useState<HistoryEntry[]>([]);
  const [chartPeriod, setChartPeriod] = useState<'24h' | '7d' | '30d' | 'all'>('all');
  
  // Forms & Loading states
  const [loading, setLoading] = useState<boolean>(false);
  const [testLoading, setTestLoading] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<ProductTestResponse | null>(null);
  const [testUrl, setTestUrl] = useState<string>('');
  
  const [targetPrice, setTargetPrice] = useState<string>('');
  const [checkInterval, setCheckInterval] = useState<number>(300);
  const [useDefaultWebhook, setUseDefaultWebhook] = useState<boolean>(true);
  const [customWebhook, setCustomWebhook] = useState<string>('');
  const [customName, setCustomName] = useState<string>('');
  
  // Settings Form
  const [settingsWebhook, setSettingsWebhook] = useState<string>('');
  const [settingsInterval, setSettingsInterval] = useState<number>(300);
  const [settingsTheme, setSettingsTheme] = useState<'light' | 'dark'>('dark');
  const [settingsCurrency, setSettingsCurrency] = useState<string>('BRL');

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [blockedRecently, setBlockedRecently] = useState<boolean>(false);
  const [intervalMinutes, setIntervalMinutes] = useState<string>('');
  const [savingInterval, setSavingInterval] = useState<boolean>(false);

  const addToast = (message: string, type: 'success' | 'error' | 'info' = 'success') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  // Load Initial Data
  const loadData = async () => {
    try {
      setLoading(true);
      const [fetchedSettings, fetchedProducts] = await Promise.all([
        fetchSettings(),
        fetchProducts()
      ]);
      setSettings(fetchedSettings);
      setMonitors(fetchedProducts);
      
      // Update form fields for settings
      setSettingsWebhook(fetchedSettings.discord_webhook || '');
      setSettingsInterval(fetchedSettings.default_check_interval || 300);
      setSettingsTheme(fetchedSettings.theme || 'dark');
      setSettingsCurrency(fetchedSettings.currency || 'BRL');
      
      // Sync dark mode HTML class
      if (fetchedSettings.theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    } catch (err: any) {
      addToast(err.message || 'Erro ao carregar dados', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Poll monitors periodically (every 10s to see updates)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const fetchedProducts = await fetchProducts();
        setMonitors(fetchedProducts);
        // If a monitor is currently selected, update it
        if (selectedMonitor) {
          const updated = fetchedProducts.find(m => m.id === selectedMonitor.id);
          if (updated) {
            setSelectedMonitor(updated);
          }
        }
      } catch (err) {}
    }, 15000);
    return () => clearInterval(interval);
  }, [selectedMonitor]);

  // Load History for selected monitor
  useEffect(() => {
    if (selectedMonitor) {
      fetchProductHistory(selectedMonitor.id)
        .then(history => setSelectedHistory(history))
        .catch(() => addToast('Erro ao carregar histórico do gráfico', 'error'));
    }
  }, [selectedMonitor]);

  // Logs do monitor (feed global) + polling
  const loadLogs = async () => {
    try {
      const res = await fetchLogs(100);
      setLogs(res.logs);
      setBlockedRecently(res.blocked_recently);
    } catch (err) {}
  };

  useEffect(() => {
    loadLogs();
    const t = setInterval(loadLogs, 15000);
    return () => clearInterval(t);
  }, []);

  // Sincroniza o editor de intervalo ao abrir um produto diferente
  useEffect(() => {
    if (selectedMonitor) {
      setIntervalMinutes(String(Math.max(1, Math.round(selectedMonitor.check_interval / 60))));
    }
  }, [selectedMonitor?.id]);

  const handleSaveInterval = async (minutes: number) => {
    if (!selectedMonitor) return;
    if (!minutes || minutes < 1) { addToast('Informe um intervalo em minutos (mínimo 1).', 'error'); return; }
    try {
      setSavingInterval(true);
      const updated = await updateProduct(selectedMonitor.id, { check_interval: Math.round(minutes * 60) });
      setSelectedMonitor(updated);
      setMonitors(prev => prev.map(m => m.id === updated.id ? updated : m));
      addToast(`Intervalo atualizado para ${minutes} min.`, 'success');
    } catch (err: any) {
      addToast(err.message || 'Erro ao atualizar intervalo', 'error');
    } finally {
      setSavingInterval(false);
    }
  };

  // Handle Testing URL
  const handleTestProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testUrl.trim()) return;
    try {
      setTestLoading(true);
      setTestResult(null);
      const result = await testProduct(testUrl);
      setTestResult(result);
      setCustomName(result.title);
      if (result.price) {
        setTargetPrice((result.price * 0.9).toFixed(2)); // Default target 10% less
      }
      addToast('Produto verificado com sucesso na Amazon!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Falha ao testar produto. Verifique a URL.', 'error');
    } finally {
      setTestLoading(false);
    }
  };

  // Create new Monitor
  const handleSaveMonitor = async () => {
    if (!testResult) return;
    try {
      setLoading(true);
      const created = await createProduct({
        url: testResult.url,
        target_price: parseFloat(targetPrice),
        check_interval: checkInterval,
        use_default_webhook: useDefaultWebhook,
        discord_webhook: useDefaultWebhook ? undefined : customWebhook,
        name: customName || testResult.title
      });
      addToast(`Monitor para "${created.name}" criado com sucesso!`, 'success');
      // Reset forms
      setTestUrl('');
      setTestResult(null);
      setTargetPrice('');
      setCustomName('');
      // Refresh list & switch tab
      await loadData();
      setActiveTab('dashboard');
    } catch (err: any) {
      addToast(err.message || 'Erro ao criar monitor', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Toggle active/paused state
  const handleToggleActive = async (monitor: Monitor) => {
    try {
      setLoading(true);
      let updated;
      if (monitor.is_active) {
        updated = await pauseProduct(monitor.id);
        addToast(`Monitor "${monitor.name}" pausado`, 'info');
      } else {
        updated = await resumeProduct(monitor.id);
        addToast(`Monitor "${monitor.name}" ativado`, 'success');
      }
      setMonitors(prev => prev.map(m => m.id === monitor.id ? updated : m));
      if (selectedMonitor && selectedMonitor.id === monitor.id) {
        setSelectedMonitor(updated);
      }
    } catch (err: any) {
      addToast(err.message || 'Erro ao alterar status', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Check price right now
  const handleCheckNow = async (id: string) => {
    try {
      setLoading(true);
      addToast('Verificando preço atual na Amazon...', 'info');
      const updated = await checkProductNow(id);
      addToast('Preço atualizado com sucesso!', 'success');
      setMonitors(prev => prev.map(m => m.id === id ? updated : m));
      if (selectedMonitor && selectedMonitor.id === id) {
        setSelectedMonitor(updated);
        const history = await fetchProductHistory(id);
        setSelectedHistory(history);
      }
    } catch (err: any) {
      addToast(err.message || 'Erro ao verificar preço', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Delete Monitor
  const handleDeleteMonitor = async (id: string) => {
    if (!confirm('Deseja realmente excluir este monitor? Todo o histórico de preços será apagado.')) return;
    try {
      setLoading(true);
      await deleteProduct(id);
      addToast('Monitor excluído com sucesso', 'success');
      setSelectedMonitor(null);
      await loadData();
    } catch (err: any) {
      addToast(err.message || 'Erro ao excluir monitor', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Save Settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const updated = await updateSettings({
        discord_webhook: settingsWebhook,
        default_check_interval: settingsInterval,
        theme: settingsTheme,
        currency: settingsCurrency
      });
      setSettings(updated);
      addToast('Configurações salvas com sucesso!', 'success');
      
      // Update HTML theme tag
      if (updated.theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    } catch (err: any) {
      addToast(err.message || 'Erro ao salvar configurações', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Filter history based on selected chart period
  const getFilteredHistory = () => {
    if (!selectedHistory.length) return [];
    const now = new Date();
    return selectedHistory.filter(h => {
      const checkDate = new Date(h.checked_at);
      const diffMs = now.getTime() - checkDate.getTime();
      if (chartPeriod === '24h') return diffMs <= 24 * 60 * 60 * 1000;
      if (chartPeriod === '7d') return diffMs <= 7 * 24 * 60 * 60 * 1000;
      if (chartPeriod === '30d') return diffMs <= 30 * 24 * 60 * 60 * 1000;
      return true;
    }).map(h => ({
      ...h,
      formattedTime: new Date(h.checked_at).toLocaleDateString('pt-BR', {
        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
      })
    }));
  };

  // Calculations derived from history
  const getAveragePrice = (history: HistoryEntry[]) => {
    const valid = history.filter(h => h.price !== undefined).map(h => h.price!);
    if (!valid.length) return 0;
    return valid.reduce((sum, val) => sum + val, 0) / valid.length;
  };

  // Indicators calculation
  const totalMonitors = monitors.length;
  const activeMonitors = monitors.filter(m => m.is_active).length;
  const triggeredAlerts = monitors.filter(m => m.alert_triggered).length;
  const errorMonitors = monitors.filter(m => m.status === 'error').length;

  const formatPrice = (price?: number) => {
    if (price === undefined || price === null) return 'N/A';
    const currencySymbol = settings?.currency === 'USD' ? '$' : 'R$';
    return `${currencySymbol} ${price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const getPriceChangePercentage = (curr?: number, prev?: number) => {
    if (!curr || !prev) return null;
    const diff = curr - prev;
    const pct = (diff / prev) * 100;
    return {
      value: Math.abs(pct).toFixed(1),
      isDown: pct < 0,
      isUp: pct > 0
    };
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-100 flex flex-col font-sans transition-colors duration-200">
      
      {/* Toast notifications container */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div 
            key={t.id} 
            className={`px-4 py-3 rounded-lg shadow-xl border text-sm font-semibold min-w-[280px] flex items-center gap-2 transform transition-all duration-300 pointer-events-auto ${
              t.type === 'success' 
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-900 dark:text-emerald-200'
                : t.type === 'error'
                ? 'bg-rose-50 border-rose-200 text-rose-800 dark:bg-rose-950 dark:border-rose-900 dark:text-rose-200'
                : 'bg-slate-50 border-slate-200 text-slate-800 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-200'
            }`}
          >
            {t.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
            {t.type === 'error' && <AlertTriangle className="w-5 h-5 text-rose-500" />}
            {t.type === 'info' && <Info className="w-5 h-5 text-sky-500" />}
            <span>{t.message}</span>
          </div>
        ))}
      </div>

      {/* Main Header */}
      <header className="bg-white border-b border-slate-200 dark:bg-slate-900 dark:border-slate-800 px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-amber-500/20">
            A
          </div>
          <div>
            <h1 className="font-extrabold text-lg tracking-tight">Monitor de Preços Amazon</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">Scraping Inteligente & Alertas em Tempo Real</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button 
            onClick={() => {
              const nextTheme = settingsTheme === 'dark' ? 'light' : 'dark';
              setSettingsTheme(nextTheme);
              updateSettings({ theme: nextTheme }).then(() => {
                if (nextTheme === 'dark') document.documentElement.classList.add('dark');
                else document.documentElement.classList.remove('dark');
                addToast(`Tema alterado para ${nextTheme === 'dark' ? 'Escuro' : 'Claro'}`, 'info');
              });
            }}
            className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
          >
            {settingsTheme === 'dark' ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="text-xs font-semibold px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-700 dark:bg-amber-950/30 dark:border-amber-900/50 dark:text-amber-300">
            {activeMonitors} / {totalMonitors} Ativos
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row">
        
        {/* Sidebar */}
        <aside className="w-full md:w-64 bg-white border-r border-slate-200 dark:bg-slate-900 dark:border-slate-800 p-4 flex flex-col gap-2">
          <button 
            onClick={() => { setActiveTab('dashboard'); setSelectedMonitor(null); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
              activeTab === 'dashboard' && !selectedMonitor
                ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/20' 
                : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400'
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            Dashboard
          </button>
          
          <button 
            onClick={() => { setActiveTab('add'); setSelectedMonitor(null); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
              activeTab === 'add' 
                ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/20' 
                : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400'
            }`}
          >
            <PlusCircle className="w-5 h-5" />
            Adicionar Monitor
          </button>

          <button 
            onClick={() => { setActiveTab('settings'); setSelectedMonitor(null); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
              activeTab === 'settings' 
                ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/20' 
                : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400'
            }`}
          >
            <SettingsIcon className="w-5 h-5" />
            Configurações
          </button>

          {/* If there is a selected monitor, show in sidebar as detail tab */}
          {selectedMonitor && (
            <div className="mt-6 border-t border-slate-200 dark:border-slate-800 pt-4">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider px-4">Monitor Selecionado</span>
              <button 
                className="w-full mt-2 flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-left text-amber-500 dark:text-amber-400"
              >
                <Eye className="w-5 h-5" />
                <span className="truncate">{selectedMonitor.name}</span>
              </button>
            </div>
          )}
        </aside>

        {/* Content Area */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">

          {/* Loader Overlay */}
          {loading && (
            <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-[2px] z-50 flex items-center justify-center">
              <div className="bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-2xl flex flex-col items-center gap-4">
                <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
                <span className="font-bold text-sm">Carregando...</span>
              </div>
            </div>
          )}

          {/* DASHBOARD TAB */}
          {activeTab === 'dashboard' && !selectedMonitor && (
            <div className="space-y-8 animate-fadeIn">
              
              {/* Counters Header */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm">
                  <span className="text-xs font-bold text-slate-400 uppercase">Total Monitorados</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-extrabold">{totalMonitors}</span>
                    <span className="text-xs text-slate-400">produtos</span>
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm">
                  <span className="text-xs font-bold text-slate-400 uppercase">Alertas Ativos</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-extrabold text-amber-500">{activeMonitors}</span>
                    <span className="text-xs text-slate-400">ativos</span>
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm">
                  <span className="text-xs font-bold text-slate-400 uppercase">Alvos Atingidos</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-extrabold text-emerald-500">{triggeredAlerts}</span>
                    <span className="text-xs text-slate-400">abaixo do alvo</span>
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm">
                  <span className="text-xs font-bold text-slate-400 uppercase">Problemas / Erros</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-extrabold text-rose-500">{errorMonitors}</span>
                    <span className="text-xs text-slate-400">consultas falhas</span>
                  </div>
                </div>
              </div>

              {/* Logs do Monitor */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Activity className="w-5 h-5 text-slate-400" />
                    <h2 className="text-xl font-bold tracking-tight">Logs do Monitor</h2>
                  </div>
                  <button onClick={loadLogs} className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 transition">
                    <RefreshCw className="w-3.5 h-3.5" /> Atualizar
                  </button>
                </div>

                {blockedRecently && (
                  <div className="mb-4 bg-rose-50 border border-rose-200 dark:bg-rose-950/30 dark:border-rose-900/60 p-4 rounded-2xl flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-sm font-bold text-rose-800 dark:text-rose-300">Possível bloqueio da Amazon</h4>
                      <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">As últimas consultas retornaram bloqueio/CAPTCHA (HTTP 403/429). O IP do servidor pode estar sendo barrado. Considere aumentar o intervalo ou usar um proxy.</p>
                    </div>
                  </div>
                )}

                <div className="max-h-[320px] overflow-y-auto space-y-2">
                  {logs.length === 0 ? (
                    <span className="text-xs text-slate-400 block text-center py-8">Nenhum log ainda. Assim que o monitor fizer consultas, elas aparecem aqui.</span>
                  ) : (
                    logs.map((log, idx) => (
                      <div key={idx} className="flex items-start gap-3 text-xs p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800/50">
                        <span className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                          log.level === 'success' ? 'bg-emerald-500'
                          : log.level === 'warning' ? 'bg-amber-500'
                          : log.level === 'blocked' ? 'bg-rose-600'
                          : 'bg-rose-400'
                        }`}></span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-bold text-slate-700 dark:text-slate-300 truncate">{log.name}</span>
                            <span className="text-[10px] text-slate-400 flex-shrink-0">{new Date(log.time).toLocaleString('pt-BR')}</span>
                          </div>
                          <span className={`block mt-0.5 ${log.level === 'blocked' || log.level === 'error' ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500 dark:text-slate-400'}`}>
                            {log.level === 'blocked' ? '🚫 ' : ''}{log.message}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Monitors List */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold tracking-tight">Produtos Cadastrados</h2>
                  <button 
                    onClick={loadData}
                    className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Atualizar
                  </button>
                </div>

                {monitors.length === 0 ? (
                  <div className="bg-white dark:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-800 rounded-3xl p-12 text-center max-w-xl mx-auto space-y-4">
                    <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto text-slate-400 dark:text-slate-600">
                      <LayoutDashboard className="w-8 h-8" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold">Nenhum monitor cadastrado</h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Adicione links da Amazon para começar a monitorar a variação de preços e receber alertas no Discord.</p>
                    </div>
                    <button 
                      onClick={() => setActiveTab('add')}
                      className="px-6 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-semibold shadow-lg shadow-amber-500/10 text-sm transition"
                    >
                      Cadastrar primeiro produto
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    {monitors.map(monitor => {
                      const pct = getPriceChangePercentage(monitor.current_price, monitor.previous_price);
                      
                      return (
                        <div 
                          key={monitor.id}
                          className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm hover:shadow-md transition flex gap-4 relative overflow-hidden"
                        >
                          {/* Left: Product Image */}
                          <div className="w-24 h-24 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center p-2 flex-shrink-0 relative">
                            {monitor.image_url ? (
                              <img src={monitor.image_url} alt={monitor.name} className="max-w-full max-h-full object-contain rounded-lg" />
                            ) : (
                              <Sparkles className="w-8 h-8 text-slate-300" />
                            )}
                            
                            {/* Target price met overlay badge */}
                            {monitor.alert_triggered && (
                              <div className="absolute -top-1.5 -left-1.5 bg-rose-500 text-white px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase shadow-sm">
                                🔥 Alvo
                              </div>
                            )}
                          </div>

                          {/* Right: details */}
                          <div className="flex-1 flex flex-col justify-between min-w-0">
                            <div>
                              <div className="flex items-start justify-between gap-2">
                                <h3 className="font-bold text-sm truncate hover:text-amber-500 transition duration-150 cursor-pointer" onClick={() => setSelectedMonitor(monitor)}>
                                  {monitor.name}
                                </h3>
                                <div className="flex-shrink-0">
                                  {/* Status badge */}
                                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                                    monitor.status === 'paused'
                                      ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                                      : monitor.status === 'target_reached'
                                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                                      : monitor.status === 'out_of_stock'
                                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
                                      : monitor.status === 'error'
                                      ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                                      : 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300'
                                  }`}>
                                    {monitor.status === 'paused' && 'Pausado'}
                                    {monitor.status === 'target_reached' && 'Alvo Atingido'}
                                    {monitor.status === 'monitoring' && 'Monitorando'}
                                    {monitor.status === 'out_of_stock' && 'Indisponível'}
                                    {monitor.status === 'error' && 'Erro'}
                                  </span>
                                </div>
                              </div>
                              <span className="text-[10px] text-slate-400 font-mono block mt-0.5">ASIN: {monitor.asin}</span>
                            </div>

                            {/* Prices row */}
                            <div className="grid grid-cols-2 gap-4 mt-2 py-1.5 border-y border-slate-100 dark:border-slate-800/80">
                              <div>
                                <span className="text-[10px] text-slate-400 font-semibold block">Preço Atual</span>
                                <span className="text-base font-extrabold block text-slate-800 dark:text-slate-100">
                                  {formatPrice(monitor.current_price)}
                                </span>
                              </div>
                              <div>
                                <span className="text-[10px] text-slate-400 font-semibold block">Preço Alvo</span>
                                <span className="text-base font-extrabold block text-amber-500">
                                  {formatPrice(monitor.target_price)}
                                </span>
                              </div>
                            </div>

                            {/* Footer info & action buttons */}
                            <div className="flex items-center justify-between mt-3 text-xs">
                              {/* Variation percentage */}
                              <div>
                                {pct ? (
                                  <div className={`flex items-center gap-1 font-bold ${pct.isDown ? 'text-emerald-500' : 'text-amber-500'}`}>
                                    {pct.isDown ? <TrendingDown className="w-3.5 h-3.5" /> : null}
                                    <span>{pct.isDown ? '↓' : '↑'} {pct.value}%</span>
                                    <span className="text-[10px] text-slate-400 font-normal">vs anterior</span>
                                  </div>
                                ) : (
                                  <span className="text-slate-400 font-medium">Sem variação</span>
                                )}
                              </div>

                              {/* Card quick actions */}
                              <div className="flex items-center gap-2">
                                <button 
                                  onClick={() => setSelectedMonitor(monitor)}
                                  title="Visualizar Detalhes & Histórico"
                                  className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 transition"
                                >
                                  <Eye className="w-4 h-4 text-slate-600 dark:text-slate-300" />
                                </button>
                                <button 
                                  onClick={() => handleCheckNow(monitor.id)}
                                  title="Verificar Preço Agora"
                                  className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 transition"
                                >
                                  <RefreshCw className="w-4 h-4 text-slate-600 dark:text-slate-300" />
                                </button>
                                <button 
                                  onClick={() => handleToggleActive(monitor)}
                                  title={monitor.is_active ? "Pausar Monitoramento" : "Retomar Monitoramento"}
                                  className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 transition"
                                >
                                  {monitor.is_active ? (
                                    <Pause className="w-4 h-4 text-amber-500" />
                                  ) : (
                                    <Play className="w-4 h-4 text-emerald-500" />
                                  )}
                                </button>
                                <button 
                                  onClick={() => handleDeleteMonitor(monitor.id)}
                                  title="Excluir Monitor"
                                  className="p-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/20 dark:hover:bg-rose-950/40 transition"
                                >
                                  <Trash2 className="w-4 h-4 text-rose-500" />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* DETAILED MONITOR VIEW */}
          {selectedMonitor && (
            <div className="space-y-8 animate-fadeIn">
              
              {/* Back to dashboard & actions header */}
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <button 
                    onClick={() => setSelectedMonitor(null)}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-xs font-bold rounded-xl transition"
                  >
                    ← Voltar à Dashboard
                  </button>
                  <h2 className="text-xl font-bold tracking-tight">Ficha Detalhada do Produto</h2>
                </div>
                
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => handleCheckNow(selectedMonitor.id)}
                    className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-amber-500/10 hover:bg-amber-600 transition"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Verificar Agora
                  </button>
                  <button 
                    onClick={() => handleToggleActive(selectedMonitor)}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-xl text-xs font-bold transition"
                  >
                    {selectedMonitor.is_active ? <Pause className="w-3.5 h-3.5 text-amber-500" /> : <Play className="w-3.5 h-3.5 text-emerald-500" />}
                    {selectedMonitor.is_active ? 'Pausar' : 'Retomar'}
                  </button>
                  <button 
                    onClick={() => handleDeleteMonitor(selectedMonitor.id)}
                    className="flex items-center gap-2 px-4 py-2 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/20 text-rose-500 rounded-xl text-xs font-bold transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Excluir
                  </button>
                </div>
              </div>

              {/* Product Profile Card */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm grid grid-cols-1 md:grid-cols-4 gap-6">
                
                {/* Image Column */}
                <div className="md:col-span-1 bg-slate-50 dark:bg-slate-800/50 rounded-2xl p-4 flex items-center justify-center max-h-64">
                  {selectedMonitor.image_url ? (
                    <img src={selectedMonitor.image_url} alt={selectedMonitor.name} className="max-w-full max-h-full object-contain rounded-xl" />
                  ) : (
                    <Sparkles className="w-16 h-16 text-slate-300" />
                  )}
                </div>

                {/* Details Column */}
                <div className="md:col-span-3 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                        selectedMonitor.status === 'paused'
                          ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                          : selectedMonitor.status === 'target_reached'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                          : 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300'
                      }`}>
                        {selectedMonitor.status === 'paused' ? 'Pausado' : 'Monitoramento Ativo'}
                      </span>
                      {selectedMonitor.availability ? (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 font-bold uppercase">
                          Em Estoque
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 font-bold uppercase">
                          Indisponível
                        </span>
                      )}
                    </div>

                    <h3 className="text-xl font-extrabold leading-tight">{selectedMonitor.name}</h3>
                    
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                      <span>ASIN: <strong className="font-mono text-slate-700 dark:text-slate-200">{selectedMonitor.asin}</strong></span>
                      <a href={selectedMonitor.url} target="_blank" rel="noopener noreferrer" className="text-amber-500 hover:underline flex items-center gap-1 font-bold">
                        Ver na Amazon <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>

                  {/* Price stats grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
                    <div>
                      <span className="text-[10px] text-slate-400 font-bold uppercase">Atual</span>
                      <span className="text-lg font-extrabold text-slate-900 dark:text-slate-100 block">
                        {formatPrice(selectedMonitor.current_price)}
                      </span>
                    </div>
                    
                    <div>
                      <span className="text-[10px] text-slate-400 font-bold uppercase">Menor</span>
                      <span className="text-lg font-extrabold text-emerald-500 block">
                        {formatPrice(selectedMonitor.lowest_price)}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-slate-400 font-bold uppercase">Maior</span>
                      <span className="text-lg font-extrabold text-slate-950 dark:text-slate-100 block">
                        {formatPrice(selectedMonitor.highest_price)}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-slate-400 font-bold uppercase">Preço Médio</span>
                      <span className="text-lg font-extrabold text-indigo-500 block">
                        {formatPrice(getAveragePrice(selectedHistory))}
                      </span>
                    </div>
                  </div>

                  {/* Dates & Cron Details */}
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-semibold text-slate-500 dark:text-slate-400">
                    <div>
                      Última consulta:{' '}
                      <span className="text-slate-800 dark:text-slate-200">
                        {selectedMonitor.last_checked_at 
                          ? new Date(selectedMonitor.last_checked_at).toLocaleString('pt-BR') 
                          : 'Nunca'}
                      </span>
                    </div>
                    <div>
                      Próxima consulta:{' '}
                      <span className="text-slate-800 dark:text-slate-200">
                        {selectedMonitor.next_check_at 
                          ? new Date(selectedMonitor.next_check_at).toLocaleString('pt-BR') 
                          : 'Agendamento Pausado'}
                      </span>
                    </div>
                  </div>

                  {/* Editor de intervalo (delay) por produto */}
                  <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="w-4 h-4 text-slate-400" />
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Intervalo de Verificação</span>
                      <span className="text-[11px] text-slate-500">(atual: a cada {Math.max(1, Math.round(selectedMonitor.check_interval / 60))} min)</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {[5, 15, 30, 60, 120, 360].map(min => (
                        <button key={min} onClick={() => handleSaveInterval(min)} disabled={savingInterval}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition disabled:opacity-50 ${
                            Math.round(selectedMonitor.check_interval / 60) === min
                              ? 'bg-amber-500 text-white border-amber-500'
                              : 'border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'
                          }`}>
                          {min < 60 ? `${min} min` : `${min / 60} h`}
                        </button>
                      ))}
                      <div className="flex items-center gap-1.5 ml-1">
                        <input type="number" min={1} value={intervalMinutes}
                          onChange={(e) => setIntervalMinutes(e.target.value)}
                          className="w-20 px-2 py-1.5 rounded-lg text-xs border border-slate-200 dark:border-slate-700 bg-transparent"
                          placeholder="min" />
                        <span className="text-xs text-slate-400">min</span>
                        <button onClick={() => handleSaveInterval(Number(intervalMinutes))} disabled={savingInterval || !intervalMinutes}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900 disabled:opacity-50">
                          {savingInterval ? 'Salvando...' : 'Salvar'}
                        </button>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-2">Intervalos muito curtos aumentam o risco de bloqueio pela Amazon. Recomendado: 30 min ou mais.</p>
                  </div>
                </div>
              </div>

              {/* Errors Section if exists */}
              {selectedMonitor.last_error && (
                <div className="bg-rose-50 border border-rose-200 dark:bg-rose-950/20 dark:border-rose-900/50 p-4 rounded-2xl flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-bold text-rose-800 dark:text-rose-300">Falha na Última Consulta</h4>
                    <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">{selectedMonitor.last_error}</p>
                    <span className="text-[10px] text-rose-500 dark:text-rose-500 block mt-2">Ocorreu em: {new Date(selectedMonitor.last_error_at!).toLocaleString()}</span>
                  </div>
                </div>
              )}

              {/* Chart & History List Section */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* Left: Recharts Pricing Chart */}
                <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm space-y-4">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <h3 className="font-extrabold text-base">Evolução do Preço</h3>
                      <p className="text-xs text-slate-400">Linha tracejada indica o seu Preço Alvo</p>
                    </div>
                    
                    {/* Period filters */}
                    <div className="flex gap-1.5 bg-slate-50 dark:bg-slate-800 p-1 rounded-xl">
                      {(['24h', '7d', '30d', 'all'] as const).map(p => (
                        <button
                          key={p}
                          onClick={() => setChartPeriod(p)}
                          className={`px-3 py-1 rounded-lg text-xs font-bold uppercase transition ${
                            chartPeriod === p
                              ? 'bg-white dark:bg-slate-900 shadow-sm text-amber-500'
                              : 'text-slate-500 dark:text-slate-400 hover:text-slate-700'
                          }`}
                        >
                          {p === 'all' ? 'Tudo' : p}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Chart representation */}
                  <div className="h-72 w-full pt-4">
                    {getFilteredHistory().length === 0 ? (
                      <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-600 gap-2 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
                        <TrendingDown className="w-8 h-8" />
                        <span className="text-xs font-bold">Histórico insuficiente para plotagem do gráfico</span>
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={getFilteredHistory()}>
                          <defs>
                            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2}/>
                              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.1} />
                          <XAxis dataKey="formattedTime" stroke="#64748b" fontSize={9} />
                          <YAxis 
                            stroke="#64748b" 
                            fontSize={9} 
                            domain={['dataMin - 10', 'dataMax + 10']}
                            tickFormatter={(v) => `${settings?.currency === 'USD' ? '$' : 'R$'} ${v}`} 
                          />
                          <Tooltip 
                            formatter={(value) => [formatPrice(Number(value)), 'Preço']} 
                            labelFormatter={(label) => `Consulta: ${label}`}
                            contentStyle={{ 
                              background: settingsTheme === 'dark' ? '#1E293B' : '#FFFFFF',
                              borderColor: settingsTheme === 'dark' ? '#334155' : '#E2E8F0',
                              borderRadius: '12px'
                            }}
                          />
                          {/* target price reference line */}
                          <ReferenceLine y={selectedMonitor.target_price} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Alvo', fill: '#ef4444', fontSize: 10, position: 'insideTopLeft' }} />
                          <Area type="monotone" dataKey="price" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#priceGrad)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>

                {/* Right: History log list */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm flex flex-col h-full max-h-[380px] overflow-hidden">
                  <h3 className="font-extrabold text-base pb-3 border-b border-slate-100 dark:border-slate-800">Registros de Consulta</h3>
                  
                  <div className="flex-1 overflow-y-auto mt-4 space-y-3">
                    {selectedHistory.length === 0 ? (
                      <span className="text-xs text-slate-400 block text-center py-8">Nenhum registro no histórico</span>
                    ) : (
                      selectedHistory.slice().reverse().map((entry, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800/50">
                          <div>
                            <span className="font-bold block text-slate-700 dark:text-slate-300">
                              {formatPrice(entry.price)}
                            </span>
                            <span className="text-[10px] text-slate-400 block mt-0.5">
                              {new Date(entry.checked_at).toLocaleString()}
                            </span>
                          </div>
                          <div>
                            <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                              entry.available 
                                ? 'bg-emerald-100/55 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
                                : 'bg-rose-100/55 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300'
                            }`}>
                              {entry.available ? 'Estoque' : 'Sem Estoque'}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* ADD MONITOR TAB */}
          {activeTab === 'add' && (
            <div className="max-w-2xl mx-auto space-y-8 animate-fadeIn">
              <div className="space-y-2">
                <h2 className="text-2xl font-extrabold tracking-tight">Adicionar Novo Monitor</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">Insira um link da Amazon e configure o valor desejado. Nós fazemos o resto.</p>
              </div>

              {/* Url Test Form */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm">
                <form onSubmit={handleTestProduct} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">URL do Produto Amazon</label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                          <Search className="w-5 h-5" />
                        </span>
                        <input 
                          type="url" 
                          placeholder="https://www.amazon.com.br/dp/B0XXXXXXXX ou similar..." 
                          value={testUrl}
                          onChange={(e) => setTestUrl(e.target.value)}
                          className="w-full pl-10 pr-4 py-3 rounded-xl bg-slate-50 border border-slate-200 dark:bg-slate-800 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                          required
                        />
                      </div>
                      <button 
                        type="submit" 
                        disabled={testLoading}
                        className="px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white dark:bg-amber-500 dark:hover:bg-amber-600 rounded-xl font-bold text-sm shadow-md transition disabled:opacity-50 flex items-center gap-2 whitespace-nowrap"
                      >
                        {testLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : null}
                        Testar Produto
                      </button>
                    </div>
                  </div>
                </form>

                {/* Scraper validation response */}
                {testResult && (
                  <div className="mt-8 border-t border-slate-100 dark:border-slate-800 pt-6 space-y-6">
                    <div className="flex gap-4 items-center">
                      <div className="w-20 h-20 bg-slate-50 dark:bg-slate-800/80 rounded-xl p-2 flex items-center justify-center flex-shrink-0">
                        {testResult.image_url ? (
                          <img src={testResult.image_url} alt={testResult.title} className="max-w-full max-h-full object-contain rounded" />
                        ) : (
                          <Sparkles className="w-8 h-8 text-slate-300" />
                        )}
                      </div>
                      <div>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 font-bold uppercase">
                          {testResult.availability ? 'Disponível' : 'Indisponível'}
                        </span>
                        <h4 className="font-bold text-sm mt-1">{testResult.title}</h4>
                        <span className="text-xs text-slate-400 font-mono">ASIN: {testResult.asin}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-50 dark:bg-slate-800/40 p-5 rounded-2xl border border-slate-100 dark:border-slate-850">
                      
                      {/* Name input */}
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Nome personalizado (Opcional)</label>
                        <input 
                          type="text" 
                          value={customName}
                          onChange={(e) => setCustomName(e.target.value)}
                          className="w-full px-4 py-2.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                        />
                      </div>

                      {/* Target Price */}
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Preço Alvo Desejado</label>
                        <div className="relative">
                          <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 font-bold text-sm">
                            {settings?.currency === 'USD' ? '$' : 'R$'}
                          </span>
                          <input 
                            type="number" 
                            step="0.01"
                            value={targetPrice}
                            onChange={(e) => setTargetPrice(e.target.value)}
                            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                            required
                          />
                        </div>
                      </div>

                      {/* Interval */}
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Intervalo de Verificação</label>
                        <select 
                          value={checkInterval}
                          onChange={(e) => setCheckInterval(parseInt(e.target.value))}
                          className="w-full px-4 py-2.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                        >
                          <option value={30}>30 segundos</option>
                          <option value={60}>1 minuto</option>
                          <option value={120}>2 minutos</option>
                          <option value={300}>5 minutos</option>
                          <option value={600}>10 minutos</option>
                          <option value={1800}>30 minutos</option>
                          <option value={3600}>1 hora</option>
                        </select>
                      </div>

                      {/* Webhook Selection */}
                      <div className="md:col-span-2">
                        <label className="flex items-center gap-2 mb-2 cursor-pointer">
                          <input 
                            type="checkbox" 
                            checked={useDefaultWebhook}
                            onChange={(e) => setUseDefaultWebhook(e.target.checked)}
                            className="w-4 h-4 rounded text-amber-500 border-slate-300 focus:ring-amber-500"
                          />
                          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 select-none">Usar Webhook padrão do Discord</span>
                        </label>
                        
                        {!useDefaultWebhook && (
                          <input 
                            type="url" 
                            placeholder="https://discord.com/api/webhooks/..." 
                            value={customWebhook}
                            onChange={(e) => setCustomWebhook(e.target.value)}
                            className="w-full px-4 py-2.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition mt-2"
                            required
                          />
                        )}
                      </div>
                    </div>

                    <div className="flex justify-end gap-3">
                      <button 
                        type="button" 
                        onClick={() => setTestResult(null)}
                        className="px-6 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-xs font-bold rounded-xl transition"
                      >
                        Cancelar
                      </button>
                      <button 
                        type="button" 
                        onClick={handleSaveMonitor}
                        className="px-6 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold shadow-lg shadow-amber-500/10 transition"
                      >
                        Salvar Monitoramento
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SETTINGS TAB */}
          {activeTab === 'settings' && (
            <div className="max-w-2xl mx-auto space-y-8 animate-fadeIn">
              <div className="space-y-2">
                <h2 className="text-2xl font-extrabold tracking-tight">Configurações Globais</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">Gerencie canais de notificação, moedas e preferências do sistema.</p>
              </div>

              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm">
                <form onSubmit={handleSaveSettings} className="space-y-6">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Webhook Discord Padrão</label>
                    <input 
                      type="url" 
                      placeholder="https://discord.com/api/webhooks/..." 
                      value={settingsWebhook}
                      onChange={(e) => setSettingsWebhook(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-slate-50 border border-slate-200 dark:bg-slate-800 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                    />
                    <span className="text-[10px] text-slate-400 block mt-1.5">Insira o link do canal do Discord para receber os alertas gerais de queda de preço.</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Intervalo Padrão de Verificação</label>
                      <select 
                        value={settingsInterval}
                        onChange={(e) => setSettingsInterval(parseInt(e.target.value))}
                        className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 dark:bg-slate-800 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                      >
                        <option value={30}>30 segundos</option>
                        <option value={60}>1 minuto</option>
                        <option value={120}>2 minutos</option>
                        <option value={300}>5 minutos</option>
                        <option value={600}>10 minutos</option>
                        <option value={1800}>30 minutos</option>
                        <option value={3600}>1 hora</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Moeda Principal</label>
                      <select 
                        value={settingsCurrency}
                        onChange={(e) => setSettingsCurrency(e.target.value)}
                        className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 dark:bg-slate-800 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm font-semibold transition"
                      >
                        <option value="BRL">Real Brasileiro (BRL - R$)</option>
                        <option value="USD">Dólar Americano (USD - $)</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex justify-end pt-4 border-t border-slate-100 dark:border-slate-800">
                    <button 
                      type="submit" 
                      className="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold text-sm shadow-md transition"
                    >
                      Salvar Alterações
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

        </main>
      </div>

    </div>
  );
}
