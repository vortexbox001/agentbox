export function Dialog({ open, onClose, title, subtitle, children, width = 560, style, ...rest }) {
  if (!open) return null;
  const backdropS = { position: 'fixed', inset: 0, background: 'var(--color-dialog-background)', backdropFilter: 'blur(8px)', zIndex: 'var(--z-modal)', display: 'flex', alignItems: 'center', justifyContent: 'center' };
  const panelS = { width: width + 'px', maxWidth: '90vw', maxHeight: '85vh', background: 'var(--color-background-default)', border: '1px solid var(--color-border-hover)', borderRadius: '12px', display: 'flex', flexDirection: 'column', boxShadow: 'var(--shadow-lg)', ...style };
  const headerS = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '20px 20px 0', gap: '12px' };
  const closeS = { width: '28px', height: '28px', borderRadius: '6px', border: 'none', background: 'var(--color-background-gray)', color: 'var(--color-text-light)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px', flexShrink: 0 };
  const bodyS = { padding: '16px 20px 20px', overflowY: 'auto', flex: 1 };
  return React.createElement('div', { style: backdropS, onClick: e => { if (e.target === e.currentTarget) onClose && onClose(); } },
    React.createElement('div', { style: panelS, ...rest },
      React.createElement('div', { style: headerS },
        React.createElement('div', null,
          title && React.createElement('div', { style: { font: 'var(--type-display-sm)', color: 'var(--color-text-default)' } }, title),
          subtitle && React.createElement('div', { style: { font: 'var(--type-body-sm)', color: 'var(--color-text-light)', marginTop: '4px' } }, subtitle)
        ),
        React.createElement('button', { onClick: onClose, style: closeS }, '\u00d7')
      ),
      React.createElement('div', { style: bodyS }, children)
    )
  );
}
