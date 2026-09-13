export function StatusDot({ status = 'idle', size = 8, style, ...rest }) {
  const colors = {
    running: 'var(--color-core-teal500)',
    success: 'var(--color-core-green500)',
    error: 'var(--color-core-red500)',
    warning: 'var(--color-core-yellow500)',
    scheduled: 'var(--color-core-lime500)',
    idle: 'var(--color-core-gray400)',
  };
  const glows = { running: 'var(--shadow-glow-teal)', success: 'none', error: 'none' };
  const s = {
    width: size + 'px', height: size + 'px', borderRadius: '50%',
    backgroundColor: colors[status] || colors.idle,
    boxShadow: glows[status] || 'none',
    flexShrink: 0, display: 'inline-block', ...style,
  };
  return React.createElement('span', { style: s, ...rest });
}
