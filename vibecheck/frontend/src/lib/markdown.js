function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function renderBasicMarkdown(input) {
  const source = typeof input === 'string' ? input : ''
  const blocks = []

  let formatted = escapeHtml(source).replace(/```([\s\S]*?)```/g, (_match, code) => {
    const placeholder = `__CODE_BLOCK_${blocks.length}__`
    blocks.push(`<pre><code>${code.trim()}</code></pre>`)
    return placeholder
  })

  formatted = formatted.replace(/`([^`\n]+)`/g, '<code>$1</code>')
  formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  formatted = formatted.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  formatted = formatted.replace(/\n/g, '<br>')

  formatted = formatted.replace(/__CODE_BLOCK_(\d+)__/g, (_match, index) => blocks[Number(index)] || '')

  return formatted
}
