export class ElementModel
{
    constructor(args) 
    {
        this.uuid = args?.uuid || '';
        this.partName = args?.partName || '';
        this.description = args?.description || '';
        this.value = args?.value || '';
        this.availability = args?.availability || '';
        this.libraryReference = args?.libraryRef || '';
        this.libraryPath = args?.libraryPath || '';
        this.footprintReferenceNo1 = args?.footprintRef1 || '';
        this.footprintPathNo1 = args?.footprintPath1 || '';
        this.footprintReferenceNo2 = args?.footprintRef2 || '';
        this.footprintPathNo2 = args?.footprintPath2 || '';
        this.footprintReferenceNo3 = args?.footprintRef3 || '';
        this.footprintPathNo3 = args?.footprintPath3 || '';
        this.createdAt = args?.created_at || '';
        this.isDatasheetSupposedToChange = args?.isDatasheetSupposedToChange || 2
        this.manufacturer = args?.manufacturer || '';
        this.suppliers = args?.suppliers || {};
        this.datasheet = args?.datasheet || false;
        this.docsCount = args?.docsCount || 0;
        this.table = args?.table || ''
    }
}

export class Manufacturer
{
    constructor(args)
    {
        this.id = args?.id || '';
        this.name = args?.name || '';
        this.createdAt = args?.createdAt || '';
    }
}

export class Supplier
{
    constructor(args)
    {
        this.id = args?.id || '';
        this.name = args?.name || '';
        this.createdAt = args?.createdAt || '';
    }
}