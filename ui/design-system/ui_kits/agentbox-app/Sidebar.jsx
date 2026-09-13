function NavItem({ icon, label, active, collapsed, onClick }) {
  const s = {
    display: 'flex', alignItems: 'center', gap: '10px',
    height: '32px', padding: collapsed ? '0' : '0 12px',
    borderRadius: '8px', cursor: 'pointer', fontSize: '14px',
    fontWeight: active ? 500 : 400, transition: 'background 100ms',
    color: active ? 'var(--color-nav-text-selected)' : 'var(--color-nav-text)',
    backgroundColor: active ? 'var(--color-translucent-teal25)' : 'transparent',
    justifyContent: collapsed ? 'center' : 'flex-start',
    width: collapsed ? '32px' : '100%',
  };
  return React.createElement('div', { style: s, onClick }, icon, !collapsed && label);
}

function NavGroup({ items, collapsed, activeKey, onNav }) {
  return React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', width: collapsed ? '32px' : '204px' } },
    items.map(it => React.createElement(NavItem, { key: it.key, icon: it.icon, label: it.label, active: activeKey === it.key, collapsed, onClick: () => onNav(it.key) }))
  );
}

function Sidebar({ activeKey, onNav, collapsed, onToggleCollapse }) {
  const iconSvg = (d) => React.createElement('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', style: { flexShrink: 0 } }, React.createElement('path', { d }));
  
  const topGroups = [
    { items: [
      { key: 'overview', label: 'Overview', icon: iconSvg('M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4') },
      { key: 'runs', label: 'Runs', icon: iconSvg('M13 10V3L4 14h7v7l9-11h-7z') },
    ]},
    { items: [
      { key: 'agents', label: 'Agents', icon: iconSvg('M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m3-3.803a4 4 0 110-5.292') },
      { key: 'templates', label: 'Templates', icon: iconSvg('M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z') },
      { key: 'schedules', label: 'Schedules', icon: iconSvg('M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z') },
    ]},
    { items: [
      { key: 'deployment', label: 'Deployment', icon: iconSvg('M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2') },
    ]},
  ];
  
  const bottomItems = [
    { key: 'search', label: 'Search', icon: iconSvg('M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z') },
    { key: 'settings', label: 'Settings', icon: iconSvg('M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z') },
  ];

  const sidebarS = {
    width: collapsed ? '68px' : '240px', height: '100%',
    backgroundColor: 'var(--color-nav-background)',
    padding: collapsed ? '16px 2px' : '16px 4px 16px 16px',
    display: 'flex', flexDirection: 'column',
    boxShadow: 'inset -1px 0 0 var(--color-keyline-default)',
    transition: 'width 200ms', overflow: 'hidden', flexShrink: 0,
  };

  const logoS = { padding: collapsed ? '0 0 12px' : '0 12px 16px', display: 'flex', alignItems: 'center', gap: '8px' };

  return React.createElement('div', { style: sidebarS },
    React.createElement('div', { style: logoS },
      React.createElement('img', { src: '../../assets/logo.svg', style: { width: '24px', height: '24px', objectFit: 'contain' } }),
      !collapsed && React.createElement('img', { src: '../../assets/wordmark.svg', alt: 'agentbox', style: { height: '18px', objectFit: 'contain' } })
    ),
    React.createElement('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' } },
      topGroups.map((g, i) => React.createElement(NavGroup, { key: i, items: g.items, collapsed, activeKey, onNav }))
    ),
    React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', paddingRight: collapsed ? 0 : '12px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)' } },
      bottomItems.map(it => React.createElement(NavItem, { key: it.key, icon: it.icon, label: it.label, collapsed, onClick: () => onNav(it.key) })),
      React.createElement(NavItem, { icon: iconSvg(collapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'), label: collapsed ? '' : 'Collapse', collapsed, onClick: onToggleCollapse })
    )
  );
}

Object.assign(window, { Sidebar });
