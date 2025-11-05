import { describe, it, expect } from 'vitest'
import { cn } from './utils'

describe('utils', () => {
  describe('cn', () => {
    it('should merge class names', () => {
      const result = cn('class1', 'class2')
      expect(result).toContain('class1')
      expect(result).toContain('class2')
    })

    it('should handle conditional classes', () => {
      const condition = false
      const result = cn('base', condition && 'hidden', 'visible')
      expect(result).toContain('base')
      expect(result).toContain('visible')
      expect(result).not.toContain('hidden')
    })

    it('should handle undefined and null', () => {
      const result = cn('class1', undefined, null, 'class2')
      expect(result).toContain('class1')
      expect(result).toContain('class2')
    })

    it('should merge Tailwind classes correctly', () => {
      // Should handle conflicting classes
      const result = cn('px-2', 'px-4')
      expect(result).toBe('px-4') // tailwind-merge should resolve conflicts
    })
  })
})
