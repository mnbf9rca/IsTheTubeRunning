import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Home from './Home';

describe('Home', () => {
  it('renders the app title', () => {
    render(<Home />);
    expect(screen.getByText('IsTheTubeRunning')).toBeInTheDocument();
  });

  it('renders the system status section', () => {
    render(<Home />);
    expect(screen.getByText('System Status')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    render(<Home />);
    expect(screen.getByText('Connecting to backend...')).toBeInTheDocument();
  });
});
