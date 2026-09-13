export function Toggle({ checked, onChange, label, disabled, style, ...rest }) {
  const wrapS = { display: 'flex', alignItems: 'center', gap: '8px', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1, ...style };
  const trackS = {
    width: '36px', height: '20px', borderRadius: '9999px', position: 'relative',
    backgroundColor: checked ? 'var(--color-core-teal500)' : 'var(--color-core-gray400)',
    transition: 'background-color 150ms', flexShrink: 0,
  };
  const thumbS = {
    width: '16px', height: '16px', borderRadius: '50%', backgroundColor: '#fff',
    position: 'absolute', top: '2px', left: checked ? '18px' : '2px',
    transition: 'left 150ms', boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
  };
  return React.createElement('label', { style: wrapS, ...rest },
    React.createElement('span', { style: trackS }, React.createElement('span', { style: thumbS })),
    label && React.createElement('span', { style: { font: 'var(--type-body-md)', color: 'var(--color-text-default)' } }, label),
    React.createElement('input', { type: 'checkbox', checked, onChange: e => onChange && onChange(e.target.checked), disabled, style: { display: 'none' } })
  );
}
