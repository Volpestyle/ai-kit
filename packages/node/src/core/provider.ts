import {
  GenerateInput,
  GenerateOutput,
  ImageGenerateInput,
  ImageGenerateOutput,
  ListModelsParams,
  MeshGenerateInput,
  MeshGenerateOutput,
  ModelMetadata,
  Provider,
  StreamChunk,
} from "./types.js";

export interface ProviderAdapter {
  readonly provider: Provider;
  listModels(params?: ListModelsParams): Promise<ModelMetadata[]>;
  generate(input: GenerateInput): Promise<GenerateOutput>;
  streamGenerate(input: GenerateInput): AsyncIterable<StreamChunk>;
  generateImage?(input: ImageGenerateInput): Promise<ImageGenerateOutput>;
  generateMesh?(input: MeshGenerateInput): Promise<MeshGenerateOutput>;
}

export type AdapterMap = Partial<Record<Provider, ProviderAdapter>>;
