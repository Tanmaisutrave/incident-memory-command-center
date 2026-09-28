import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { api } from '../../services/api';

export default function Layout() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [memoryStats, setMemoryStats] = useState(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const health = await api.getHealth();
        setSystemHealth(health);
      } catch (error) {
        console.error('Failed to fetch system health:', error);
      }
    };

    const fetchMemoryStats = async () => {
      try {
        const stats = await api.getMemoryStats();
        setMemoryStats(stats);
      } catch (error) {
        console.error('Failed to fetch memory stats:', error);
      }
    };

    fetchHealth();
    fetchMemoryStats();

    // Refresh health every 30 seconds
    const healthInterval = setInterval(fetchHealth, 30000);
    const statsInterval = setInterval(fetchMemoryStats, 60000);

    return () => {
      clearInterval(healthInterval);
      clearInterval(statsInterval);
    };
  }, []);

  return (
    <div className="flex h-screen bg-background text-white">
      <Sidebar systemHealth={systemHealth} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header memoryStats={memoryStats} />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
