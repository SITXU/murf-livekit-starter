import { Button } from '@/components/ui/button';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  hasDisconnected?: boolean;
  microphoneError?: string | null;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  hasDisconnected = false,
  microphoneError = null,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref}>
      <section className="bg-background flex flex-col items-center justify-center text-center">
        <img src="/anisha-logo.jpg" alt="Anisha Logo" className="mb-4 size-24 rounded-full border-4 border-[var(--accent)] shadow-lg" />

        <h1 className="text-2xl font-bold text-foreground mb-2">Anisha</h1>
        <p className="text-foreground max-w-prose pt-1 leading-6 font-medium">
          {hasDisconnected ? "Call ended. Start again?" : "Your Voice Assistant for Financial Literacy"}
        </p>

        {microphoneError && (
          <div className="mt-4 p-4 bg-red-100 text-red-800 rounded-md max-w-md mx-auto text-sm">
            <p className="font-bold">Microphone Error</p>
            <p>{microphoneError}</p>
            <p className="mt-2 text-xs">Please check your browser settings and allow microphone access to talk to Anisha.</p>
          </div>
        )}

        <Button
          size="lg"
          onClick={onStartCall}
          className="mt-6 w-64 rounded-full font-mono text-xs font-bold tracking-wider uppercase bg-[var(--accent)] hover:opacity-90 transition-opacity"
        >
          {startButtonText}
        </Button>
      </section>
    </div>
  );
};
