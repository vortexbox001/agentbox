export function RunStatusTag({ status = 'success', label, style, ...rest }) {
  const map = {
    success: { bg: 'var(--color-background-green)', dot: 'var(--color-accent-green)' },
    failure: { bg: 'var(--color-background-red)', dot: 'var(--color-accent-red)' },
    error: { bg: 'var(--color-background-red)', dot: 'var(--color-accent-red)' },
    started: { bg: 'var(--color-background-gray)', dot: 'var(--color-text-light)' },
    running: { bg: 'var(--color-background-gray)', dot: 'var(--color-text-light)' },
    queued: { bg: 'var(--color-background-gray)', dot: 'var(--color-text-lighter)' },
    canceled: { bg: 'var(--color-background-yellow)', dot: 'var(--color-accent-yellow)' },
  };
  const c = map[status] || map.success;
  const s = { display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '3px 9px', borderRadius: '8px', background: c.bg, whiteSpace: 'nowrap', ...style };
  return React.createElement('span', { style: s, ...rest },
    React.createElement('span', { style: { width: '7px', height: '7px', borderRadius: '50%', background: c.dot, flexShrink: 0 } }),
    React.createElement('span', { style: { font: 'var(--type-body-sm)', color: 'var(--color-text-default)', fontWeight: 500 } }, label || status)
  );
}
