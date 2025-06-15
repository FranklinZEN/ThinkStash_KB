import { useState, useCallback } from 'react';

type ActionState<TInput, TOutput> = {
  fieldErrors?: {
    [key in keyof TInput]?: string[];
  };
  error?: string | null;
  data?: TOutput;
};

type Action<TInput, TOutput> = (
  data: TInput
) => Promise<ActionState<TInput, TOutput>>;

type UseActionOptions<TOutput> = {
  onSuccess?: (data: TOutput) => void;
  onError?: (error: string) => void;
  onComplete?: () => void;
};

export const useAction = <TInput, TOutput>(
  action: Action<TInput, TOutput>,
  options: UseActionOptions<TOutput> = {}
) => {
  const [fieldErrors, setFieldErrors] =
    useState<ActionState<TInput, TOutput>['fieldErrors']>(undefined);
  const [error, setError] =
    useState<ActionState<TInput, TOutput>['error']>(undefined);
  const [data, setData] =
    useState<ActionState<TInput, TOutput>['data']>(undefined);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const execute = useCallback(
    async (input: TInput) => {
      setIsLoading(true);

      try {
        const result = await action(input);
        if (!result) {
          return;
        }
        
        setFieldErrors(result.fieldErrors);
        setError(result.error);
        
        if (result.data) {
          setData(result.data);
          options.onSuccess?.(result.data);
        }
        
        if (result.error) {
            options.onError?.(result.error);
        }

      } finally {
        setIsLoading(false);
        options.onComplete?.();
      }
    },
    [action, options]
  );

  return {
    execute,
    fieldErrors,
    error,
    data,
    isLoading,
  };
}; 