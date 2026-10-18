import { createRuntimeEndpointAdapterFacet, runtimeConfigExact, runtimeConfigObject,
  runtimeConfigString } from '@hypit/hypit/runtime-kit';
import { createLibTVProvider, providerModule } from './provider.mjs';

export default {
  format: 'hypit.node-package@1',
  hostFacets: [createRuntimeEndpointAdapterFacet({
    use: providerModule.name,
    activate(context) {
      const config = runtimeConfigObject(context.config, 'LibTV');
      runtimeConfigExact(config, ['prepared', 'evidenceDirectory', 'authorization', 'executable', 'ffprobe'], 'LibTV');
      const options = Object.fromEntries(Object.entries(config).map(([key, value]) =>
        [key, runtimeConfigString(value, `LibTV ${key}`)]));
      if (!options.prepared || !options.evidenceDirectory || !context.pool)
        throw new Error('LibTV requires prepared, evidenceDirectory and a capacity pool.');
      return { endpoint: createLibTVProvider({ ...options, instance: context.instance, pool: context.pool }) };
    },
  })],
};
