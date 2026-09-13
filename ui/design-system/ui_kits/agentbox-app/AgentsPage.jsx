function AgentsPage() {
  const ns = window.AgentBoxDesignSystem_463fbd || {};
  const Badge = ns.Badge || (() => null);
  const StatusDot = ns.StatusDot || (() => null);

  const [tab, setTab] = React.useState('all');

  const agents = [
    { name: 'summarizer-v2', model: 'gpt-4o', status: 'running', runs: 124, lastRun: '2m ago', schedule: 'Every 30min', tokens: '45.2k' },
    { name: 'code-reviewer', model: 'claude-3.5-sonnet', status: 'success', runs: 89, lastRun: '1h ago', schedule: 'On push', tokens: '128k' },
    { name: 'data-cleaner', model: 'gpt-4o-mini', status: 'error', runs: 45, lastRun: '3h ago', schedule: 'Daily 2am', tokens: '12.8k' },
    { name: 'report-writer', model: 'gpt-4o', status: 'scheduled', runs: 67, lastRun: '6h ago', schedule: 'Weekly Mon', tokens: '89.1k' },
    { name: 'ticket-triage', model: 'claude-3.5-sonnet', status: 'success', runs: 201, lastRun: '15m ago', schedule: 'Every 5min', tokens: '340k' },
    { name: 'doc-indexer', model: 'gpt-4o-mini', status: 'idle', runs: 12, lastRun: '2d ago', schedule: 'Manual', tokens: '5.6k' },
  ];

  const headerS = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' };
  const titleS = { font: 'var(--type-display-lg)', color: 'var(--color-text-default)' };
  const btnS = {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    padding: '6px 12px', borderRadius: '8px', border: 'none',
    background: 'var(--color-accent-primary)', color: 'var(--color-accent-reversed)',
    fontSize: '14px', fontWeight: 400, cursor: 'pointer', fontFamily: 'var(--font-default)',
  };
  const tabBarS = { display: 'flex', gap: '16px', borderBottom: '1px solid var(--color-keyline-default)', marginBottom: '16px' };
  const tabBtnS = (active) => ({
    background: 'none', border: 'none', padding: '12px 0', fontFamily: 'var(--font-default)',
    fontSize: '14px', fontWeight: 600, cursor: 'pointer',
    color: active ? 'var(--color-text-default)' : 'var(--color-text-light)',
    boxShadow: active ? 'var(--color-text-default) 0 -2px 0 inset' : 'none',
  });
  const gridHeaderS = {
    display: 'grid', gridTemplateColumns: '2fr 1fr 100px 80px 100px 100px',
    gap: '0', padding: '8px 12px', borderBottom: '1px solid var(--color-keyline-default)',
  };
  const thS = { font: 'var(--type-label-sm)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--color-text-lighter)' };
  const rowS = {
    display: 'grid', gridTemplateColumns: '2fr 1fr 100px 80px 100px 100px',
    gap: '0', padding: '12px', borderBottom: '1px solid var(--color-keyline-default)',
    cursor: 'pointer', transition: 'background 100ms',
  };
  const nameS = { display: 'flex', alignItems: 'center', gap: '10px' };

  const statCards = [
    { label: 'Total Agents', value: '6', delta: null },
    { label: 'Active Runs', value: '2', delta: '+1' },
    { label: 'Success Rate', value: '94%', delta: '+2.1%' },
    { label: 'Tokens Today', value: '621k', delta: null },
  ];

  const statS = {
    background: 'var(--color-background-default)', border: '1px solid var(--color-border-default)',
    borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '4px',
  };

  return React.createElement('div', { style: { padding: '24px', height: '100%', overflowY: 'auto' } },
    React.createElement('div', { style: headerS },
      React.createElement('span', { style: titleS }, 'Agents'),
      React.createElement('button', { style: btnS },
        React.createElement('svg', { width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, React.createElement('path', { d: 'M12 5v14m-7-7h14' })),
        'New Agent'
      )
    ),
    // Stat cards
    React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '20px' } },
      statCards.map((s, i) => React.createElement('div', { key: i, style: statS },
        React.createElement('div', { style: { font: 'var(--type-label-sm)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--color-text-lighter)' } }, s.label),
        React.createElement('div', { style: { display: 'flex', alignItems: 'baseline', gap: '8px' } },
          React.createElement('span', { style: { font: 'var(--type-display-xl)', color: 'var(--color-text-default)' } }, s.value),
          s.delta && React.createElement('span', { style: { font: 'var(--type-mono-sm)', color: 'var(--color-text-green)' } }, s.delta)
        )
      ))
    ),
    // Tabs
    React.createElement('div', { style: tabBarS },
      ['all', 'running', 'scheduled', 'failed'].map(t =>
        React.createElement('button', { key: t, style: tabBtnS(tab === t), onClick: () => setTab(t) },
          t.charAt(0).toUpperCase() + t.slice(1),
          t === 'all' && React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 500, padding: '0 5px', background: 'var(--color-background-gray)', borderRadius: '4px', marginLeft: '6px' } }, agents.length)
        )
      )
    ),
    // Table header
    React.createElement('div', { style: gridHeaderS },
      ['Agent', 'Model', 'Status', 'Runs', 'Schedule', 'Last Run'].map(h => React.createElement('div', { key: h, style: thS }, h))
    ),
    // Table rows
    agents.map((a, i) => React.createElement('div', { key: i, style: rowS },
      React.createElement('div', { style: nameS },
        React.createElement(StatusDot, { status: a.status, size: 8 }),
        React.createElement('span', { style: { fontWeight: 500 } }, a.name)
      ),
      React.createElement('div', { style: { font: 'var(--type-mono-sm)', color: 'var(--color-text-light)' } }, a.model),
      React.createElement('div', null, React.createElement(Badge, { label: a.status, intent: a.status === 'idle' ? 'default' : a.status })),
      React.createElement('div', { style: { font: 'var(--type-mono-sm)', color: 'var(--color-text-default)' } }, a.runs),
      React.createElement('div', { style: { font: 'var(--type-body-sm)', color: 'var(--color-text-light)' } }, a.schedule),
      React.createElement('div', { style: { font: 'var(--type-mono-xs)', color: 'var(--color-text-lighter)' } }, a.lastRun)
    ))
  );
}

Object.assign(window, { AgentsPage });
