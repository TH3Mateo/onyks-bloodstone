import axios from 'axios';

const api = axios.create(
{
  baseURL: '/api',
  timeout: 5000,
  headers: 
  {
    'Content-Type': 'application/json',
    // 'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
});

export const repository = 
{
    name: async () =>
    {
        try 
        {
            const response = await api.get(`/repository/name`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    list: async (path) =>
    {
        try 
        {
            const response = await api.get(`/repository/list`,
            {
                params: 
                {
                    path: path
                }
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    statistics: async () => 
    {
        try 
        {
            // The first call after a commit re-parses every library file, which can
            // take longer than the default 5 s timeout.
            const response = await api.get(`/repository/statistics`, { timeout: 120000 });
            return response
        } 
        catch (error) 
        {
            return error
        }
    }
}

export const element = 
{
    lastAdded: async () =>
    {
        try 
        {
            const response = await api.get(`/element/last-added`);
            return response
        } 
        catch (error)
        {
            console.dir(error)
            return error
        }
    },
    number: async (since = null) =>
    {
        try 
        {
            const response = await api.get(`/element/number`, {
                params: { since: since ? since.toISOString() : undefined }
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    create: async (element, datasheet = null) =>
    {
        try 
        {
            const formData = new FormData();

            formData.append('element', JSON.stringify(element));

            if (datasheet)
            {
                formData.append('datasheet', datasheet);
            }

            const response = await api.post(`/element/create`, formData,
            {
                headers: {'Content-Type': 'multipart/form-data'} 
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    duplicate: async (id, element, datasheet = null) =>
    {
        try 
        {
            const formData = new FormData();

            formData.append('element', JSON.stringify(element));

            if (datasheet)
            {
                formData.append('datasheet', datasheet);
            }

            const response = await api.post(`/element/duplicate/${id}`, formData,
            {
                headers: {'Content-Type': 'multipart/form-data'} 
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    get: async (id) =>
    {
        try 
        {
            const response = await api.get(`/element/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    list: async (limit, skip, search = null, tables = null) =>
    {
        try
        {
            const response = await api.get(`/element/list`, {
                params: {
                    limit: limit,
                    skip: skip,
                    search: search || undefined,
                    tables: (tables && tables.length) ? tables.join(',') : undefined
                }
            });
            return response
        }
        catch (error)
        {
            return error
        }
    },
    edit: async (id, element, datasheet = null) =>
    {
        try 
        {
            const formData = new FormData();
            formData.append('element', JSON.stringify(element));

            if (datasheet)
            {
                formData.append('datasheet', datasheet);
            }

            const response = await api.put(`/element/edit/${id}`, formData,
            {
                headers: {'Content-Type': 'multipart/form-data'}
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    delete: async (id) =>
    {
        try 
        {
            const response = await api.delete(`/element/delete/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    openDatasheet: (uuid) =>
    {
        window.open(`/files/${uuid}.pdf`, '_blank');
    }
}

// Additional documents are stored as <uuid>_1.pdf .. <uuid>_N.pdf next to the main
// datasheet; the element's docsCount is the only thing kept in the database.
export const elementDocument =
{
    upload: async (elementUuid, file) =>
    {
        try
        {
            const formData = new FormData();
            formData.append('file', file);

            const response = await api.post(`/element/${elementUuid}/documents`, formData,
            {
                headers: {'Content-Type': 'multipart/form-data'}
            });
            return response
        }
        catch (error)
        {
            return error
        }
    },
    delete: async (elementUuid, index) =>
    {
        try
        {
            const response = await api.delete(`/element/${elementUuid}/documents/${index}`);
            return response
        }
        catch (error)
        {
            return error
        }
    },
    open: (elementUuid, index) =>
    {
        window.open(`/files/${elementUuid}_${index}.pdf`, '_blank');
    }
}

export const table = 
{
    number: async () =>
    {
        try 
        {
            const response = await api.get(`/table/number`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    numbers: async () =>
    {
        try 
        {
            const response = await api.get(`/table/numbers`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    create: async (table) =>
    {
        try 
        {
            const response = await api.post(`/table/create`, table);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    get: async (id) =>
    {
        try 
        {
            const response = await api.get(`/table/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    list: async (limit, skip) =>
    {
        try 
        {
            const response = await api.get(`/table/list`, {
                params: {
                    limit: limit,
                    skip: skip
                }
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    edit: async (id, table) =>
    {
        try 
        {
            const response = await api.put(`/table/edit/${id}`, table);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    delete: async (id) =>
    {
        try 
        {
            const response = await api.delete(`/table/delete/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    }
}

export const manufacturer = 
{
    number: async () =>
    {
        try 
        {
            const response = await api.get(`/manufacturer/number`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    numbers: async () =>
    {
        try 
        {
            const response = await api.get(`/manufacturer/numbers`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    create: async (element) =>
    {
        try 
        {
            const response = await api.post(`/manufacturer/create`, element);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    get: async (id) =>
    {
        try 
        {
            const response = await api.get(`/manufacturer/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    list: async (limit, skip) =>
    {
        try 
        {
            const response = await api.get(`/manufacturer/list`, {
                params: {
                    limit: limit,
                    skip: skip
                }
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    edit: async (id, manufacturer) =>
    {
        try 
        {
            const response = await api.put(`/manufacturer/edit/${id}`, manufacturer);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    delete: async (id) =>
    {
        try 
        {
            const response = await api.delete(`/manufacturer/delete/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    }
}

export const supplier = 
{
    number: async () =>
    {
        try 
        {
            const response = await api.get(`/supplier/number`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    create: async (element) =>
    {
        try 
        {
            const response = await api.post(`/supplier/create`, element);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    list: async (limit, skip) =>
    {
        try 
        {
            const response = await api.get(`/supplier/list`, {
                params: {
                    limit: limit,
                    skip: skip
                }
            });
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    delete: async (id) =>
    {
        try 
        {
            const response = await api.delete(`/supplier/delete/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    edit: async (id, supplier) =>
    {
        try 
        {
            const response = await api.put(`/supplier/edit/${id}`, supplier);
            return response
        } 
        catch (error) 
        {
            return error
        }
    },
    get: async (id) =>
    {
        try 
        {
            const response = await api.get(`/supplier/${id}`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    }
}

export const settings =
{
    identity: async () =>
    {
        try
        {
            const response = await api.get(`/server/identity`);
            return response
        }
        catch (error)
        {
            return error
        }
    },
    downloadDbLib: () =>
    {
        window.open('/api/settings/dblib', '_blank');
    },
    downloadKicadDbl: () =>
    {
        window.open('/api/settings/kicad-dbl', '_blank');
    }
}

export const other =
{
    updateViews: async () =>
    {
        try 
        {
            const response = await api.post(`/update-views`);
            return response
        } 
        catch (error) 
        {
            return error
        }
    }
}