export function Summary({ html, fallback }) {
  if (html) {
    return React.createElement('div', {
      className: 'ax-summary', dangerouslySetInnerHTML: { __html: html },
    });
  }
  return React.createElement('div', { className: 'ax-summary ax-summary--empty' }, fallback);
}
