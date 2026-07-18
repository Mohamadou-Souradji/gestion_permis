import { IAuthority, NewAuthority } from './authority.model';

export const sampleWithRequiredData: IAuthority = {
  name: '919bcb07-b222-404f-bf4d-2502f4911007',
};

export const sampleWithPartialData: IAuthority = {
  name: '7ff89eca-6a99-49ce-85dc-24c6f4d73184',
};

export const sampleWithFullData: IAuthority = {
  name: 'fc7b0c23-4431-46e4-98d9-48952a7d8fde',
};

export const sampleWithNewData: NewAuthority = {
  name: null,
};

Object.freeze(sampleWithNewData);
Object.freeze(sampleWithRequiredData);
Object.freeze(sampleWithPartialData);
Object.freeze(sampleWithFullData);
