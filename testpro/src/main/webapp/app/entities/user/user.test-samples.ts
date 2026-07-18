import { IUser } from './user.model';

export const sampleWithRequiredData: IUser = {
  id: 10806,
  login: 'KtfI0',
};

export const sampleWithPartialData: IUser = {
  id: 31492,
  login: 'eed-@2\\=nBz1j\\Ol2poE8',
};

export const sampleWithFullData: IUser = {
  id: 22178,
  login: 'oTt-@HNvw\\}hsO',
};
Object.freeze(sampleWithRequiredData);
Object.freeze(sampleWithPartialData);
Object.freeze(sampleWithFullData);
