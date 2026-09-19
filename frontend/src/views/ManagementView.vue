<script setup>
    import WarningAlert from '@/components/WarningAlert.vue'
    import BasicButtonsPanel from '@/components/BasicButtonsPanel.vue'
    import BasicTable from '@/components/BasicTable.vue'
    import {onMounted, ref, toRaw, watch, inject} from 'vue'
    import { manufacturer, supplier, table, element } from '@/utils/api'
    import AddItemDialog from '@/components/AddItemDialog.vue'
    import EditItemDialog from '@/components/EditItemDialog.vue'
    import DeleteItemDialog from '@/components/DeleteItemDialog.vue'
    import { LabelsDoc } from '@/utils/tools'
    import { useRouter } from 'vue-router'
    import ColumnsCheckboxes from '@/components/ColumnsCheckboxes.vue'
    import CategoryFilter from '@/components/CategoryFilter.vue'
    import { readStorage, writeStorage } from '@/utils/storage.js'

    const router = useRouter()

    const fullWidth = inject('fullWidth')
    const toggleFullWidth = inject('toggleFullWidth')

    const elementsSearch = ref(readStorage('onyks-management-search', ''))
    const elementsSelectedTables = ref(readStorage('onyks-management-tables', null))
    const elementsAvailableTables = ref([])

    const elementsListUpdate = (limit, skip) =>
        element.list(limit, skip, elementsSearch.value, elementsSelectedTables.value)

    const loadElementsAvailableTables = async () =>
    {
        let data = await table.numbers()
        if (data.status == 200)
        {
            elementsAvailableTables.value = Object.keys(data.data)
        }
    }

    let elementsSearchDebounce = null
    watch(elementsSearch, (value) =>
    {
        writeStorage('onyks-management-search', value)
        clearTimeout(elementsSearchDebounce)
        elementsSearchDebounce = setTimeout(() => elements.value.table?.init(), 300)
    })

    watch(elementsSelectedTables, (value) =>
    {
        writeStorage('onyks-management-tables', value)
        elements.value.table?.init()
    })

    const elements = ref({
        table: null,
        columns: [
            {
                "key": "selected",
                "label": "Select",
            },
            {
                "key": "uuid",
                "label": "UUID",
                "hidden": false
            },
            {
                "key": "partName",
                "label": "Part Name",
                "hidden": false
            },
            {
                "key": "manufacturer",
                "label": "Manufacturer",
                "hidden": false
            },
            {
                "key": "table",
                "label": "Table",
                "hidden": false
            },
            {
                "key": "description",
                "label": "Description",
                "hidden": false
            },
            {
                "key": "value",
                "label": "Value",
                "hidden": false
            },
            {
                "key": "availability",
                "label": "Availability",
                "hidden": false
            },
            {
                "key": "libraryReference",
                "label": "Symbol Reference",
                "hidden": false
            },
            {
                "key": "libraryPath",
                "label": "Symbol Path",
                "hidden": false
            },
            {
                "key": "footprintReferenceNo1",
                "label": "Footprint Reference No. 1",
                "hidden": false
            },
            {
                "key": "footprintPathNo1",
                "label": "Footprint Path No. 1",
                "hidden": false
            },
            {
                "key": "footprintReferenceNo2",
                "label": "Footprint Reference No. 2",
                "hidden": false
            },
            {
                "key": "footprintPathNo2",
                "label": "Footprint Path No. 2",
                "hidden": false
            },
            {
                "key": "footprintReferenceNo3",
                "label": "Footprint Reference No. 3",
                "hidden": false
            },
            {
                "key": "footprintPathNo3",
                "label": "Footprint Path No. 3",
                "hidden": false
            },
            {
                "key": "createdAt",
                "label": "Created At",
                "hidden": false
            },
        ],
        disabled:
        {
            edit: true,
            delete: true,
            duplicate: true,
            datasheet: true,
            labels: true,
            details: true
        },
        disable: (e) =>
        {
            switch(e)
            {
                case 0:
                    elements.value.disabled.edit = true
                    elements.value.disabled.delete = true
                    elements.value.disabled.duplicate = true
                    elements.value.disabled.datasheet = true
                    elements.value.disabled.labels = true
                    elements.value.disabled.details = true
                    break;
                case 1:
                    elements.value.disabled.edit = false
                    elements.value.disabled.delete = false
                    elements.value.disabled.duplicate = false
                    elements.value.disabled.datasheet = false
                    elements.value.disabled.labels = false
                    elements.value.disabled.details = false
                    break;
                default:
                    elements.value.disabled.edit = true
                    elements.value.disabled.delete = false
                    elements.value.disabled.duplicate = true
                    elements.value.disabled.datasheet = true
                    elements.value.disabled.labels = false
                    elements.value.disabled.details = true
                    break;
            }
        },
        action: async (type) =>
        {
            let data = null
            switch(type)
            {
                case 'add':
                    router.push('/element/add')
                    break;
                case 'edit':
                    router.push(`/element/edit/${elements.value.table.getSelectedRows()[0].uuid}`)
                    break;
                case 'delete':
                    elements.value.dialogs.delete.open(elements.value.table.getSelectedRows())
                    break;
                case 'duplicate':
                    router.push(`/element/duplicate/${elements.value.table.getSelectedRows()[0].uuid}`)
                    break;
                case 'datasheet':
                    data = elements.value.table.getSelectedRows()[0]
                    if(data.datasheet)
                    {
                        element.openDatasheet(data.uuid)
                    }
                    else
                    {
                        
                    }
                    break;
                case 'labels':
                    data = elements.value.table.getSelectedRows()
                    let total = data.length
                
                    let doc = new LabelsDoc(total)
                    await doc.init()

                    for(let i=0; i<total; i++)
                    {
                        await doc.drawData(i, data[i])
                        await doc.drawQR(i, data[i].uuid)
                    }

                    await doc.drawBorders()
                    await doc.finish()
                    break;
                case 'details':
                    router.push(`/element/details/${elements.value.table.getSelectedRows()[0].uuid}`)
                    break;
                default:
                    break;
            }
        },
        dialogs:
        {
            add: null,
            edit: null,
            delete: null
        },
        success: () =>
        {
            elements?.value.table?.init()
            elements.value.disabled.edit = true
            elements.value.disabled.delete = true
            elements.value.updateColumns()
        },
        updateColumns: async () =>
        {
            let data = await supplier.list()
            let temp = toRaw(elements.value.columns)
            temp = [...temp.filter(column => !column.key.startsWith('supplier_'))]

            data.data.items.forEach(element => 
            {
                temp.push({
                    "key": `supplier_${element.id}`,
                    "label": `Supplier - ${element.name}`,
                    "hidden": false
                })
            });

            elements.value.columns = [...temp]
        }
    })

    const tables = ref({
        table: null,
        columns: [
            {
                "key": "selected",
                "label": "Select"
            },
            {
                'key': 'id',
                'label': 'ID'
            },
            {
                "key": "name",
                "label": "Name"
            },
            {
                "key": "createdAt",
                "label": "Created At"
            },
        ],
        disabled:
        {
            edit: true,
            delete: true
        },
        disable: () =>
        {
            switch(tables.value.table.getSelectedRows().length)
            {
                case 0:
                    tables.value.disabled.edit = true
                    tables.value.disabled.delete = true
                    break;
                case 1:
                    tables.value.disabled.edit = false
                    tables.value.disabled.delete = false
                    break;
                default:
                    tables.value.disabled.edit = true
                    tables.value.disabled.delete = false
                    break;
            }
        },
        action: (type) =>
        {
            let data = null
            switch(type)
            {
                case 'add':
                    tables.value.dialogs.add.open()
                    break;
                case 'edit':
                    data = tables.value.table.getSelectedRows()[0]
                    tables.value.dialogs.edit.open(data.name, data.id)
                    break;
                case 'delete':
                    data = tables.value.table.getSelectedRows()
                    tables.value.dialogs.delete.open(data)
                    break;
                default:
                    break;
            }
        },
        dialogs:
        {
            add: null,
            edit: null,
            delete: null
        },
        success: () =>
        {
            tables?.value.table?.init()
            tables.value.disabled.edit = true
            tables.value.disabled.delete = true
        }
    })

    const suppliers = ref({
        table: null,
        columns: [
            {
                "key": "selected",
                "label": "Select"
            },
            {
                'key': 'id',
                'label': 'ID'
            },
            {
                "key": "name",
                "label": "Name"
            },
            {
                "key": "createdAt",
                "label": "Created At"
            },
        ],
        disabled:
        {
            edit: true,
            delete: true
        },
        disable: () =>
        {
            switch(suppliers.value.table.getSelectedRows().length)
            {
                case 0:
                    suppliers.value.disabled.edit = true
                    suppliers.value.disabled.delete = true
                    break;
                case 1:
                    suppliers.value.disabled.edit = false
                    suppliers.value.disabled.delete = false
                    break;
                default:
                    suppliers.value.disabled.edit = true
                    suppliers.value.disabled.delete = false
                    break;
            }
        },
        action: (type) =>
        {
            let data = null
            switch(type)
            {
                case 'add':
                    suppliers.value.dialogs.add.open()
                    break;
                case 'edit':
                    data = suppliers.value.table.getSelectedRows()[0]
                    suppliers.value.dialogs.edit.open(data.name, data.id)
                    break;
                case 'delete':
                    data = suppliers.value.table.getSelectedRows()
                    suppliers.value.dialogs.delete.open(data)
                    break;
                default:
                    break;
            }
        },
        dialogs:
        {
            add: null,
            edit: null,
            delete: null
        },
        success: () =>
        {
            suppliers?.value.table?.init()
            suppliers.value.disabled.edit = true
            suppliers.value.disabled.delete = true
        }
    })

    const manufacturers = ref({
        table: null,
        columns: [
            {
                "key": "selected",
                "label": "Select"
            },
            {
                'key': 'id',
                'label': 'ID'
            },
            {
                "key": "name",
                "label": "Name"
            },
            {
                "key": "createdAt",
                "label": "Created At"
            },
        ],
        disabled:
        {
            edit: true,
            delete: true
        },
        disable: () =>
        {
            switch(manufacturers.value.table.getSelectedRows().length)
            {
                case 0:
                    manufacturers.value.disabled.edit = true
                    manufacturers.value.disabled.delete = true
                    break;
                case 1:
                    manufacturers.value.disabled.edit = false
                    manufacturers.value.disabled.delete = false
                    break;
                default:
                    manufacturers.value.disabled.edit = true
                    manufacturers.value.disabled.delete = false
                    break;
            }
        },
        action: (type) =>
        {
            let data = null
            switch(type)
            {
                case 'add':
                    manufacturers.value.dialogs.add.open()
                    break;
                case 'edit':
                    data = manufacturers.value.table.getSelectedRows()[0]
                    manufacturers.value.dialogs.edit.open(data.name, data.id)
                    break;
                case 'delete':
                    data = manufacturers.value.table.getSelectedRows()
                    manufacturers.value.dialogs.delete.open(data)
                    break;
                default:
                    break;
            }
        },
        dialogs:
        {
            add: null,
            edit: null,
            delete: null
        },
        success: () =>
        {
            manufacturers?.value.table?.init()
            manufacturers.value.disabled.edit = true
            manufacturers.value.disabled.delete = true
        }
    })

    const success = () =>
    {
        elements.value.success()
        tables.value.success()
        manufacturers.value.success()
        suppliers.value.success()
    }

    onMounted(() =>
    {
        manufacturers.value.table.init()
        suppliers.value.table.init()
        tables.value.table.init()
        elements.value.table.init()
        elements.value.updateColumns()
        loadElementsAvailableTables()
    })
</script>

<template>
    <onyks-container gap="l" padding="l">

        <onyks-header>Management</onyks-header>
        <WarningAlert></WarningAlert>
        <onyks-button icon="F6AE" background="yellow" class="qrScan" size="xl"></onyks-button>

        <!-- ELEMENTS -->
        <onyks-header level="3">Elements</onyks-header>

        <onyks-textfield size="m" placeholder="Search elements..." type="text" v-model="elementsSearch"></onyks-textfield>

        <CategoryFilter :names="elementsAvailableTables" v-model="elementsSelectedTables"></CategoryFilter>

        <ColumnsCheckboxes
            :model-value="elements?.columns.slice(1)"
            :table="elements.table"
            @update:model-value="(columns) => { if (elements) elements.columns = [elements.columns[0], ...columns] }">
        </ColumnsCheckboxes>

        <onyks-button size="s" background="blue" @click="toggleFullWidth">{{ fullWidth ? 'Collapse table' : 'Expand table' }}</onyks-button>

        <BasicTable :ref="(el) => { if (el && elements) elements.table = el }"
                :columns="elements?.columns"
                :update="elementsListUpdate"
                @checkbox-click="elements?.disable"></BasicTable>

        <BasicButtonsPanel>
            <onyks-button background="green"
                @click="() => elements.action('add')">Add</onyks-button>
            <onyks-button background="blue"
                @click="() => elements.action('edit')"
                :disabled="elements?.disabled.edit">Edit</onyks-button>
            <onyks-button
                @click="() => elements.action('delete')"
                :disabled="elements?.disabled.delete">Delete</onyks-button>

            <onyks-button background="yellow"
                @click="() => elements.action('duplicate')"
                :disabled="elements?.disabled.duplicate">Duplicate</onyks-button>

            <onyks-button background="green"
                @click="() => elements.action('datasheet')"
                :disabled="elements?.disabled.datasheet">Datasheet</onyks-button>

            <onyks-button background="blue"
                @click="() => elements.action('labels')"
                :disabled="elements?.disabled.labels">Labels</onyks-button>

            <onyks-button background="red"
                @click="() => elements.action('details')"
                :disabled="elements?.disabled.details">Details</onyks-button>
        </BasicButtonsPanel>

        <DeleteItemDialog
            subject="element(s)"
            :processor="(item) => item.uuid"
            :ref="(el) => { if (el && elements) elements.dialogs.delete = el }"
            :action="element.delete"
            :formater="(item) => item.partName"
            @success="success">
            <template v-slot:top>
                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
            </template>
        </DeleteItemDialog>

        <!-- TABLES -->
        <onyks-header level="3">Tables</onyks-header>
        <BasicButtonsPanel>
            <onyks-button background="green" 
                @click="() => tables.action('add')">Add</onyks-button>
            <onyks-button background="blue"
                @click="() => tables.action('edit')" 
                :disabled="tables?.disabled.edit">Edit</onyks-button>
            <onyks-button
                @click="() => tables.action('delete')"
                :disabled="tables?.disabled.delete">Delete</onyks-button>
        </BasicButtonsPanel>

        <BasicTable :ref="(el) => { if (el && tables) tables.table = el }" 
                :columns="tables?.columns"
                :update="table.list"
                @checkbox-click="tables?.disable"></BasicTable>
        
        <AddItemDialog subject="table" 
            :ref="(el) => { if (el && tables) tables.dialogs.add = el }"
            :action="table.create"
            @success="success">
        </AddItemDialog>

        <EditItemDialog subject="table"
            :ref="(el) => { if (el && tables) tables.dialogs.edit = el }"
            :action="table.edit"
            @success="success">
        </EditItemDialog>

        <DeleteItemDialog
            subject="table(s)"
            :processor="(item) => item.id"
            :ref="(el) => { if (el && tables) tables.dialogs.delete = el }"
            :action="table.delete"
            :formater="(item) => item.name"
            @success="success">
            <template v-slot:top>
                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
            </template>
        </DeleteItemDialog>

        <!-- MANUFACTURER -->
        <onyks-header level="3">Manufacturers</onyks-header>
        <BasicButtonsPanel>
            <onyks-button background="green" 
                @click="() => manufacturers.action('add')">Add</onyks-button>
            <onyks-button background="blue"
                @click="() => manufacturers.action('edit')" 
                :disabled="manufacturers?.disabled.edit">Edit</onyks-button>
            <onyks-button
                @click="() => manufacturers.action('delete')"
                :disabled="manufacturers?.disabled.delete">Delete</onyks-button>
        </BasicButtonsPanel>

        <BasicTable :ref="(el) => { if (el && manufacturers) manufacturers.table = el }" 
                :columns="manufacturers?.columns"
                :update="manufacturer.list"
                @checkbox-click="manufacturers?.disable"></BasicTable>
        
        <AddItemDialog subject="manufacturer" 
            :ref="(el) => { if (el && manufacturers) manufacturers.dialogs.add = el }"
            :action="manufacturer.create"
            @success="success">
        </AddItemDialog>

        <EditItemDialog subject="manufacturer"
            :ref="(el) => { if (el && manufacturers) manufacturers.dialogs.edit = el }"
            :action="manufacturer.edit"
            @success="success">
        </EditItemDialog>

        <DeleteItemDialog
            subject="manufacturer(s)"
            :processor="(item) => item.id"
            :ref="(el) => { if (el && manufacturers) manufacturers.dialogs.delete = el }"
            :action="manufacturer.delete"
            :formater="(item) => item.name"
            @success="success">
            <template v-slot:top>
                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
            </template>
        </DeleteItemDialog>

        <!-- SUPPLIER -->
        <onyks-header level="3">Suppliers</onyks-header>
        <BasicButtonsPanel>
            <onyks-button background="green" 
                @click="() => suppliers.action('add')">Add</onyks-button>
            <onyks-button background="blue"
                @click="() => suppliers.action('edit')" 
                :disabled="suppliers?.disabled.edit">Edit</onyks-button>
            <onyks-button
                @click="() => suppliers.action('delete')"
                :disabled="suppliers?.disabled.delete">Delete</onyks-button>
        </BasicButtonsPanel>

        <BasicTable :ref="(el) => { if (el && suppliers) suppliers.table = el }" 
                :columns="suppliers?.columns"
                :update="supplier.list"
                @checkbox-click="suppliers?.disable"></BasicTable>
        
        <AddItemDialog subject="supplier" 
            :ref="(el) => { if (el && suppliers) suppliers.dialogs.add = el }"
            :action="supplier.create"
            @success="success">
        </AddItemDialog>

        <EditItemDialog subject="supplier"
            :ref="(el) => { if (el && suppliers) suppliers.dialogs.edit = el }"
            :action="supplier.edit"
            @success="success">
        </EditItemDialog>

        <DeleteItemDialog
            subject="supplier(s)"
            :processor="(item) => item.id"
            :ref="(el) => { if (el && suppliers) suppliers.dialogs.delete = el }"
            :action="supplier.delete"
            :formater="(item) => item.name"
            @success="success">
            <template v-slot:top>
                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
            </template>
        </DeleteItemDialog>
        
    </onyks-container>
</template>

<style>
    .qrScan
    {
        width: fit-content;
        position: fixed;
        right: 0;
        bottom: 0;
        margin: var(--onyks-spacing-md);
        z-index: 100;
        display: none;
    }

    onyks-textfield
    {
        width: 100%;
        max-width: 400px;
    }
</style>