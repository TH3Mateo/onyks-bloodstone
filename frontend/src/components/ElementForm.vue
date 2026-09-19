<script setup>
    import { useWindowSize } from '@vueuse/core';
    import ValueSelector from './ValueSelector.vue';
    import { ref, computed } from 'vue';
    import { manufacturer, table, supplier } from '@/utils/api.js';
    import AddItemDialog from './AddItemDialog.vue';
    import EditItemDialog from './EditItemDialog.vue';
    import DeleteItemDialog from './DeleteItemDialog.vue';
    import RepositoryModelSelector from './RepositoryModelSelector.vue';
    import SuppliersSelector from './SuppliersSelector.vue';
    import DatasheetPicker from './DatasheetPicker.vue';
    import ElementDocuments from './ElementDocuments.vue';
    import { element } from '@/utils/api.js';
    import { useRoute } from 'vue-router';
    const route = useRoute()

    const {width} = useWindowSize()
    const props = defineProps(['type'])
    const model = defineModel({ data: Object })
    const file = defineModel('file')
    const selectors = ref({manufacturer: null, supplier: null, table: null})
    const dialogs = ref({manufacturer: {add: null, edit: null, delete: null}, 
    table: {add: null, edit: null, delete: null}, supplier: {add: null, edit: null, delete: null}, library: null, footprint1: null, footprint2: null, footprint3: null})
    const filters = ref(
    {
        footprint: (e) => 
        {
            return e.type == 'dir' || e.type == 'pcblib' || e.type == 'footprint'
        },
        symbol: (e) =>
        {
            return e.type == 'dir' || e.type == 'schlib' || e.type == 'symbol'
        }
    })

    const symbolFilled = computed(() => !!model.value.libraryReference && !!model.value.libraryPath)
    const footprint1Filled = computed(() => !!model.value.footprintReferenceNo1 && !!model.value.footprintPathNo1)
    const footprint2Filled = computed(() => !!model.value.footprintReferenceNo2 && !!model.value.footprintPathNo2)

</script>

<template>
    <onyks-container gap="m" type="stack" padding="">

        <!-- TOP: compact single-line fields, side by side -->
        <onyks-container gap="m" type="grid" :cols="width > 900 ? 4 : width > 550 ? 2 : 1" padding="">

            <onyks-container gap="s" padding="" :class="{ 'field-wide': width > 550 }">
                <onyks-text size="m">Part Name</onyks-text>
                <onyks-textfield :disabled="props.type === 'details'" size="m" maxlength="256" placeholder="Part Name" type="text" v-model="model.partName"></onyks-textfield>
            </onyks-container>

            <onyks-container gap="s" padding="" :class="{ 'field-wide': width > 550 }">
                <onyks-text size="m">Value</onyks-text>
                <onyks-textfield :disabled="props.type === 'details'" size="m" maxlength="256" placeholder="Value" type="text" v-model="model.value"></onyks-textfield>
            </onyks-container>

            <onyks-container gap="s" padding="">
                <onyks-text size="m">Availability</onyks-text>
                <onyks-textfield :disabled="props.type === 'details'" size="m" maxlength="256" placeholder="Availability" type="text" v-model="model.availability"></onyks-textfield>
            </onyks-container>

            <onyks-container gap="s" padding="" v-if="props.type == 'details' || props.type == 'edit'">
                <onyks-text size="m">UUID</onyks-text>
                <onyks-textfield disabled size="m" type="text" v-model="model.uuid"></onyks-textfield>
            </onyks-container>

            <onyks-container gap="s" padding="" v-if="props.type == 'details'">
                <onyks-text size="m">Created At</onyks-text>
                <onyks-textfield disabled size="m" type="text" v-model="model.createdAt"></onyks-textfield>
            </onyks-container>
        </onyks-container>

        <!-- Description: compact, full width -->
        <onyks-container gap="s" padding="">
            <onyks-text size="m">Description</onyks-text>
            <onyks-textarea
                size="m"
                placeholder="Description"
                v-model="model.description"
                rows="3"
                cols="100"
                minlength="0"
                maxlength="256"
                :disabled="props.type === 'details'"
                resize="none">
            </onyks-textarea>
        </onyks-container>

        <!-- MAIN: left = Symbol & Footprints (+ Datasheet), right = Manufacturer/Category/Suppliers -->
        <onyks-container gap="m" type="grid" :cols="width > 900 ? 2 : 1" padding="">

            <!-- LEFT -->
            <onyks-card title="Symbol &amp; Footprints" size="l">
                <onyks-container gap="s" padding="">

                    <!-- Symbol -->
                    <onyks-container gap="s" type="grid" :cols="width > 500 ? 2 : 1" padding="">
                        <onyks-textfield disabled size="m" placeholder="Symbol Reference" type="text" v-model="model.libraryReference"></onyks-textfield>
                        <onyks-textfield disabled size="m" placeholder="Symbol Path" type="text" v-model="model.libraryPath"></onyks-textfield>
                    </onyks-container>
                    <onyks-button v-if="props.type != 'details'" background="blue" @click="dialogs?.library?.open">Select Symbol</onyks-button>

                    <RepositoryModelSelector v-if="props.type != 'details'" :filter="filters.symbol"
                        title="symbol" :ref="(el) => { if (el && dialogs) dialogs.library = el }"
                        @model-select="(e) => {model.libraryReference = e.name; model.libraryPath = e.path.join('/')}">
                    </RepositoryModelSelector>

                    <hr>

                    <!-- Footprint No. 1 -->
                    <onyks-container gap="s" type="grid" :cols="width > 500 ? 2 : 1" padding="">
                        <onyks-textfield size="m" placeholder="Footprint 1 Reference" disabled type="text" v-model="model.footprintReferenceNo1"></onyks-textfield>
                        <onyks-textfield size="m" placeholder="Footprint 1 Path" type="text" disabled v-model="model.footprintPathNo1"></onyks-textfield>
                    </onyks-container>
                    <onyks-button v-if="props.type != 'details'" background="yellow" @click="dialogs?.footprint1?.open">Select Footprint 1</onyks-button>

                    <RepositoryModelSelector v-if="props.type != 'details'" :filter="filters.footprint"
                    title="footprint no. 1" :ref="(el) => { if (el) dialogs.footprint1 = el }"
                    @model-select="(e) => {model.footprintReferenceNo1 = e.name; model.footprintPathNo1 = e.path.join('/')}">
                    </RepositoryModelSelector>

                    <!-- Footprint No. 2 (only once footprint 1 + symbol are set) -->
                    <onyks-container gap="s" type="grid" :cols="width > 500 ? 2 : 1" padding="" v-if="footprint1Filled && symbolFilled">
                        <onyks-textfield size="m" disabled placeholder="Footprint 2 Reference" type="text" v-model="model.footprintReferenceNo2"></onyks-textfield>
                        <onyks-textfield size="m" disabled placeholder="Footprint 2 Path" type="text" v-model="model.footprintPathNo2"></onyks-textfield>
                    </onyks-container>
                    <onyks-button v-if="props.type != 'details' && footprint1Filled && symbolFilled" background="yellow" @click="dialogs?.footprint2.open()">Select Footprint 2</onyks-button>

                    <RepositoryModelSelector v-if="props.type != 'details' && footprint1Filled && symbolFilled" :filter="filters.footprint"
                    title="footprint no. 2" :ref="(el) => { if (el) dialogs.footprint2 = el }"
                    @model-select="(e) => {model.footprintReferenceNo2 = e.name; model.footprintPathNo2 = e.path.join('/')}">
                    </RepositoryModelSelector>

                    <!-- Footprint No. 3 (only once footprint 2 is set too) -->
                    <onyks-container gap="s" type="grid" :cols="width > 500 ? 2 : 1" padding="" v-if="footprint1Filled && symbolFilled && footprint2Filled">
                        <onyks-textfield size="m" disabled placeholder="Footprint 3 Reference" type="text" v-model="model.footprintReferenceNo3"></onyks-textfield>
                        <onyks-textfield size="m" placeholder="Footprint 3 Path" disabled type="text" v-model="model.footprintPathNo3"></onyks-textfield>
                    </onyks-container>
                    <onyks-button v-if="props.type != 'details' && footprint1Filled && symbolFilled && footprint2Filled" background="yellow" @click="dialogs?.footprint3.open()">Select Footprint 3</onyks-button>

                    <RepositoryModelSelector v-if="props.type != 'details' && footprint1Filled && symbolFilled && footprint2Filled" :filter="filters.footprint"
                    title="footprint no. 3" :ref="(el) => { if (el) dialogs.footprint3 = el }"
                    @model-select="(e) => {model.footprintReferenceNo3 = e.name; model.footprintPathNo3 = e.path.join('/')}">
                    </RepositoryModelSelector>

                    <hr>

                    <!-- Datasheet -->
                    <onyks-container gap="s" type="stack" padding="">
                        <onyks-text size="m">Datasheet</onyks-text>
                        <onyks-text v-if="props.type == 'details' && !model.datasheet">Not available.</onyks-text>
                        <onyks-button v-else-if="props.type == 'details' && model.datasheet" @click="model.datasheet? element.openDatasheet(route.params.uuid): null">Open</onyks-button>
                        <onyks-container gap="s" type="stack" padding="" v-if="props.type == 'add' || props.type == 'duplicate' || props.type == 'edit'">
                            <DatasheetPicker :datasheet="model.datasheet" :type="props.type" v-model:file="file" v-model:mode="model.isDatasheetSupposedToChange"></DatasheetPicker>
                        </onyks-container>
                    </onyks-container>

                    <hr>

                    <!-- Additional documents (application notes, register maps, etc.) -->
                    <onyks-container gap="s" type="stack" padding="">
                        <onyks-text size="m">Additional Documents</onyks-text>
                        <onyks-text v-if="props.type == 'add' || props.type == 'duplicate'" size="m">Save the element first to add additional documents.</onyks-text>
                        <ElementDocuments v-else
                            :element-uuid="route.params.uuid"
                            :docs-count="model.docsCount"
                            :disabled="props.type === 'details'"
                            @change="(value) => model.docsCount = value">
                        </ElementDocuments>
                    </onyks-container>

                </onyks-container>
            </onyks-card>

            <!-- RIGHT -->
            <onyks-container gap="m" type="stack" padding="">

                <onyks-card title="Manufacturer" size="m">
                    <onyks-container gap="s" padding="">
                        <onyks-text size="m" v-if="props.type != 'details'">Selected: {{ model.manufacturer  || 'Undefined'}}</onyks-text>

                        <ValueSelector :ref="(el) => { if (el && selectors) selectors.manufacturer = el }"
                            @add-click="dialogs?.manufacturer?.add?.open"
                            @edit-click="() => {dialogs.manufacturer.edit.open(selectors.manufacturer.name, selectors.manufacturer.id)}"
                            @delete-click="() => {dialogs.manufacturer.delete.open([{name: selectors.manufacturer.name, id: selectors.manufacturer.id}])}"
                            :action="manufacturer.list" v-model:name="model.manufacturer"
                            v-if="props.type != 'details'" subject="manufacturer">
                        </ValueSelector>

                        <onyks-textfield v-else :disabled="props.type === 'details'"
                            size="m" placeholder="Manufacturer" type="text"
                            v-model="model.manufacturer">
                        </onyks-textfield>

                        <AddItemDialog subject="manufacturer"
                            :ref="(el) => { if (el && dialogs) dialogs.manufacturer.add = el }"
                            :action="manufacturer.create"
                            @success="selectors?.manufacturer?.reset">
                        </AddItemDialog>

                        <EditItemDialog subject="manufacturer"
                            :ref="(el) => { if (el && dialogs) dialogs.manufacturer.edit = el }"
                            :action="manufacturer.edit"
                            @success="selectors?.manufacturer?.reset">
                        </EditItemDialog>

                        <DeleteItemDialog
                            subject="manufacturer(s)"
                            :processor="(item) => item.id"
                            :ref="(el) => { if (el && dialogs) dialogs.manufacturer.delete = el }"
                            :action="manufacturer.delete"
                            :formater="(item) => item.name"
                            @success="selectors?.manufacturer?.reset">
                            <template v-slot:top>
                                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
                            </template>
                        </DeleteItemDialog>
                    </onyks-container>
                </onyks-card>

                <onyks-card title="Category" size="m">
                    <onyks-container gap="s" padding="">
                        <onyks-text size="m" v-if="props.type != 'details'">Selected: {{ model.table  || 'Undefined'}}</onyks-text>
                        <ValueSelector :ref="(el) => { if (el && selectors) selectors.table = el }"
                            @add-click="dialogs?.table?.add?.open"
                            @edit-click="() => {dialogs.table.edit.open(selectors.table.name, selectors.table.id)}"
                            @delete-click="() => {dialogs.table.delete.open([{name: selectors.table.name, id: selectors.table.id}])}"
                            :action="table.list" v-model:name="model.table"
                            v-if="props.type != 'details'" subject="table">
                        </ValueSelector>

                        <AddItemDialog subject="table"
                            :ref="(el) => { if (el && dialogs) dialogs.table.add = el }"
                            :action="table.create"
                            @success="selectors?.table?.reset">
                        </AddItemDialog>

                        <EditItemDialog subject="table"
                            :ref="(el) => { if (el && dialogs) dialogs.table.edit = el }"
                            :action="table.edit"
                            @success="selectors?.table?.reset">
                        </EditItemDialog>

                        <DeleteItemDialog
                            subject="table(s)"
                            :processor="(item) => item.id"
                            :ref="(el) => { if (el && dialogs) dialogs.table.delete = el }"
                            :action="table.delete"
                            :formater="(item) => item.name"
                            @success="selectors?.table?.reset">
                            <template v-slot:top>
                                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
                            </template>
                        </DeleteItemDialog>

                        <onyks-textfield v-if="props.type == 'details'" :disabled="props.type === 'details'"
                            size="m" placeholder="Table" type="text"
                            v-model="model.table">
                        </onyks-textfield>
                    </onyks-container>
                </onyks-card>

                <onyks-card title="Suppliers" size="m">
                    <onyks-container gap="s" padding="">
                        <SuppliersSelector @add-click="dialogs?.supplier?.add?.open" :ref="(el) => { if (el && selectors) selectors.supplier = el }"
                            @edit-click="() => {dialogs.supplier.edit.open(selectors.supplier.name, selectors.supplier.id)}"
                            @delete-click="() => {dialogs.supplier.delete.open([{name: selectors.supplier.name, id: selectors.supplier.id}])}"
                            :action="supplier.list" v-model:codes="model.suppliers"
                             subject="supplier" :disabled="props.type === 'details'">
                        </SuppliersSelector>

                        <AddItemDialog subject="supplier"
                            :ref="(el) => { if (el && dialogs) dialogs.supplier.add = el }"
                            :action="supplier.create"
                            @success="selectors?.supplier?.reset">
                        </AddItemDialog>

                        <EditItemDialog subject="supplier"
                            :ref="(el) => { if (el && dialogs) dialogs.supplier.edit = el }"
                            :action="supplier.edit"
                            @success="selectors?.supplier?.reset">
                        </EditItemDialog>

                        <DeleteItemDialog
                            subject="supplier(s)"
                            :processor="(item) => item.id"
                            :ref="(el) => { if (el && dialogs) dialogs.supplier.delete = el }"
                            :action="supplier.delete"
                            :formater="(item) => item.name"
                            @success="selectors?.supplier?.reset">
                            <template v-slot:top>
                                <onyks-alert type="warning">This operation cannot be undone.</onyks-alert>
                            </template>
                        </DeleteItemDialog>
                    </onyks-container>
                </onyks-card>

            </onyks-container>

        </onyks-container>

    </onyks-container>

</template>

<style scoped>
    .field-wide
    {
        grid-column: span 2;
    }

    onyks-textfield
    {
        width: 100%;
    }

    onyks-button
    {
        width: 100%;
    }

    onyks-textarea
    {
        width: 100%;
    }

    onyks-card
    {
        width: 100%;
        box-sizing: border-box;
    }

    hr
    {
        width: 100%;
        border: none;
        border-top: 1px solid var(--onyks-surface-1-border);
        margin: var(--onyks-spacing-sm) 0;
    }
</style>